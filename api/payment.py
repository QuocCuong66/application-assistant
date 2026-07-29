from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import RedirectResponse
import datetime
import urllib.parse
import uuid
from bson import ObjectId

from database import get_db
from schemas import PaymentCreateRequest, PaymentUrlResponse
from api.deps import get_current_user
from api.vnpay_utils import generate_vnpay_signature, verify_vnpay_signature
from config import VNPAY_TMN_CODE, VNPAY_URL, VNPAY_RETURN_URL

router = APIRouter(prefix="/payment", tags=["payment"])

@router.post("/create_url", response_model=PaymentUrlResponse)
def create_payment_url(
    request: PaymentCreateRequest,
    fastapi_req: Request,
    db = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    # Create order_id (must be unique)
    order_id = str(uuid.uuid4()).replace("-", "")[:15]

    # Save transaction as PENDING
    transaction_doc = {
        "user_id": current_user["id"],
        "order_id": order_id,
        "amount": request.amount,
        "status": "PENDING",
        "created_at": datetime.datetime.now(datetime.timezone.utc)
    }
    transactions = db.transactions
    result = transactions.insert_one(transaction_doc)

    # Prepare VNPay parameters
    vnp_Params = {
        "vnp_Version": "2.1.0",
        "vnp_Command": "pay",
        "vnp_TmnCode": VNPAY_TMN_CODE,
        "vnp_Amount": str(request.amount * 100), # VNPay expects amount * 100
        "vnp_CurrCode": "VND",
        "vnp_TxnRef": order_id,
        "vnp_OrderInfo": f"Upgrade PRO for {current_user.get('username', 'user')}",
        "vnp_OrderType": "other",
        "vnp_Locale": "vn",
        "vnp_ReturnUrl": VNPAY_RETURN_URL,
        "vnp_IpAddr": fastapi_req.client.host,
        "vnp_CreateDate": datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    }

    # Generate signature
    secure_hash = generate_vnpay_signature(vnp_Params)
    vnp_Params["vnp_SecureHash"] = secure_hash

    # Create final URL
    query_string = urllib.parse.urlencode(vnp_Params)
    payment_url = f"{VNPAY_URL}?{query_string}"

    return PaymentUrlResponse(url=payment_url)


@router.get("/vnpay_return")
def vnpay_return(request: Request, db = Depends(get_db)):
    vnp_Params = dict(request.query_params)

    if "vnp_SecureHash" not in vnp_Params:
        return RedirectResponse(url="/?payment=failed_no_signature")

    vnp_SecureHash = vnp_Params["vnp_SecureHash"]

    # Verify signature
    if not verify_vnpay_signature(vnp_Params, vnp_SecureHash):
        return RedirectResponse(url="/?payment=failed_invalid_signature")

    order_id = vnp_Params.get("vnp_TxnRef")
    response_code = vnp_Params.get("vnp_ResponseCode")

    # Find transaction
    transactions = db.transactions
    transaction = transactions.find_one({"order_id": order_id})
    if not transaction:
        return RedirectResponse(url="/?payment=failed_not_found")

    if transaction.get("status") == "SUCCESS":
        return RedirectResponse(url="/?payment=success")

    if response_code == "00":
        # Payment success
        transactions.update_one({"_id": transaction["_id"]}, {"$set": {"status": "SUCCESS"}})

        # Upgrade user to Pro
        users = db.users
        user_id = transaction["user_id"]  # This is a string from our schema
        users.update_one({"_id": ObjectId(user_id)}, {"$set": {"is_pro": True}})

        return RedirectResponse(url="/?payment=success")
    else:
        # Payment failed
        transactions.update_one({"_id": transaction["_id"]}, {"$set": {"status": "FAILED"}})
        return RedirectResponse(url="/?payment=failed")
