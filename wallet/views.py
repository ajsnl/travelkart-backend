from django.shortcuts import render
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django.conf import settings
from django.db import transaction
import decimal
import hmac
import hashlib
import base64
import requests
import random

from .models import Wallet, WalletTransaction

class UserWalletView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        transactions = WalletTransaction.objects.filter(user=request.user, status='success')

        txn_type = request.query_params.get('type')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')

        if txn_type and txn_type.upper() in ['CREDIT', 'DEBIT']:
            transactions = transactions.filter(transaction_type=txn_type.upper())

        from django.utils.dateparse import parse_date
        if start_date:
            parsed_start = parse_date(start_date)
            if parsed_start:
                transactions = transactions.filter(created_at__date__gte=parsed_start)

        if end_date:
            parsed_end = parse_date(end_date)
            if parsed_end:
                transactions = transactions.filter(created_at__date__lte=parsed_end)

        transactions = transactions.order_by('-created_at')
        return Response({
            "balance": wallet.balance,
            "transactions": [
                {
                    "id": t.id,
                    "amount": t.amount,
                    "transaction_type": t.transaction_type,
                    "reason": t.reason,
                    "created_at": t.created_at,
                } for t in transactions
            ]
        })

class AddWalletMoneyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        amount = request.data.get('amount')
        if not amount:
            raise ValidationError({"error": "amount is required."})
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError()
        except ValueError:
            raise ValidationError({"error": "Invalid amount specified."})

        key_id = getattr(settings, 'RAZORPAY_KEY_ID', None)
        key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', None)
        if not key_id or not key_secret or key_id.startswith('dummy') or key_secret.startswith('dummy'):
            raise ValidationError({"error": "Razorpay payment credentials are not configured on the server. Please contact support."})

        try:
            auth_str = f"{key_id}:{key_secret}"
            base64_auth = base64.b64encode(auth_str.encode('ascii')).decode('ascii')
            headers = {
                "Authorization": f"Basic {base64_auth}",
                "Content-Type": "application/json"
            }
            receipt = f"WLT-{random.randint(100000, 999999)}"
            payload = {
                "amount": int(amount * 100),
                "currency": "INR",
                "receipt": receipt
            }
            response = requests.post("https://api.razorpay.com/v1/orders", headers=headers, json=payload, timeout=10)
            if response.status_code in [200, 201]:
                razorpay_order_id = response.json().get('id')
            else:
                raise ValidationError({"error": f"Razorpay order initialization failed with status {response.status_code}: {response.text}"})
        except requests.RequestException as e:
            raise ValidationError({"error": f"Network error connecting to Razorpay: {str(e)}"})
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError({"error": f"An error occurred: {str(e)}"})

        WalletTransaction.objects.create(
            user=request.user,
            amount=amount,
            transaction_type='CREDIT',
            reason='Add Money',
            status='pending',
            razorpay_order_id=razorpay_order_id
        )

        return Response({
            "razorpay_order_id": razorpay_order_id,
            "amount": amount,
            "currency": "INR",
            "razorpay_key_id": key_id
        })

class VerifyWalletPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        razorpay_payment_id = request.data.get('razorpay_payment_id')
        razorpay_order_id = request.data.get('razorpay_order_id')
        razorpay_signature = request.data.get('razorpay_signature')

        if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
            raise ValidationError({"error": "razorpay_payment_id, razorpay_order_id, and razorpay_signature are required."})

        try:
            transaction_obj = WalletTransaction.objects.get(
                razorpay_order_id=razorpay_order_id,
                user=request.user,
                status='pending'
            )
        except WalletTransaction.DoesNotExist:
            raise ValidationError({"error": "Pending wallet transaction not found."})

        key_secret = getattr(settings, 'RAZORPAY_KEY_SECRET', None)
        if not key_secret or key_secret == 'dummy_key_secret':
            raise ValidationError({"error": "Razorpay credentials are not configured on the server."})

        msg = f"{razorpay_order_id}|{razorpay_payment_id}"
        generated_signature = hmac.new(
            key=key_secret.encode('utf-8'),
            msg=msg.encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()

        if hmac.compare_digest(generated_signature, razorpay_signature):
            with transaction.atomic():
                wallet, _ = Wallet.objects.select_for_update().get_or_create(user=request.user)
                wallet.balance += decimal.Decimal(transaction_obj.amount)
                wallet.save()

                transaction_obj.status = 'success'
                transaction_obj.razorpay_payment_id = razorpay_payment_id
                transaction_obj.razorpay_signature = razorpay_signature
                transaction_obj.save()
            return Response({"status": "success", "message": "Funds added successfully to wallet.", "balance": wallet.balance})
        else:
            transaction_obj.status = 'failed'
            transaction_obj.save()
            return Response({"status": "failed", "message": "Payment signature verification failed."}, status=400)


      
