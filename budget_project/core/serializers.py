from rest_framework import serializers
from .models import Receipt, QRPayment, MobileNotification, VoiceTransaction, DeviceToken, Transaction, Category

class ReceiptSerializer(serializers.ModelSerializer):
    class Meta:
        model = Receipt
        fields = ['id', 'image', 'ocr_text', 'processed', 'created_at', 'total_amount', 'merchant_name', 'receipt_date']
        read_only_fields = ['ocr_text', 'processed', 'total_amount', 'merchant_name', 'receipt_date']

class QRPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = QRPayment
        fields = ['id', 'qr_code', 'amount', 'description', 'category', 'created_at', 'expires_at', 'used']
        read_only_fields = ['qr_code', 'used']

class MobileNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MobileNotification
        fields = ['id', 'type', 'title', 'message', 'created_at', 'read', 'sent', 'scheduled_for']
        read_only_fields = ['created_at', 'sent']

class VoiceTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = VoiceTransaction
        fields = ['id', 'audio_file', 'transcription', 'processed', 'created_at', 'transaction']
        read_only_fields = ['transcription', 'processed', 'transaction']

class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ['id', 'token', 'device_type', 'created_at', 'last_used', 'is_active']
        read_only_fields = ['created_at', 'last_used'] 