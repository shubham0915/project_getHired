import sys
import os
import json
import io
import pandas as pd
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from core.pipeline import MaskingPipeline

csv_text = """request_id,ts,user_id,method,endpoint,http_status,latency_ms,partner_bank,idempotency_key,error_msg
REQ935461491035,2025-05-31 17:16:23.000,USR000972,GET,/cbs/transaction/{id}/status,200,139,CANB,IDM8859665068,
REQ935461491036,2025-05-31 17:16:25.000,USR000973,POST,/cbs/transfer/initiate,500,452,HDFC,IDM8859665069,Payment failed for Aadhaar 849312345678 due to timeout
REQ935461491037,2025-05-31 17:16:28.000,USR000974,GET,/cbs/user/profile,404,89,ICICI,IDM8859665070,User profile for rajesh.sharma@example.com not found in backend DB
REQ935461491038,2025-05-31 17:16:32.000,USR000975,POST,/cbs/auth/otp,401,210,SBI,IDM8859665071,Invalid OTP sent to +91 9876543210
"""

df = pd.read_csv(io.StringIO(csv_text))
pipeline = MaskingPipeline(enable_ner=True)
masked_df, manifest = pipeline.process(df)

print(masked_df.to_csv(index=False))
