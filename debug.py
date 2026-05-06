import pandas as pd
from core.pipeline import MaskingPipeline
import logging

logging.basicConfig(level=logging.DEBUG)

df = pd.DataFrame({
    'Tracking_Number': ['123456789012', '111122223333'],
    'Account_Number': ['SUCCESS', 'FAILED'],
    'Customer_acc_num': [
        'Customer Anjali asked to update PAN to BXKPR9211M and card to 4111222233334444.',
        'Send refund to UPI ID anj123@okhdfcbank or IFSC HDFC0001234.'
    ],
    'Amount': ['1000', '2500']
})

p = MaskingPipeline(enable_ner=False)
masked, _ = p.process(df)
print(masked.to_csv(index=False))

p_ner = MaskingPipeline(enable_ner=False)
# Manually test text
print("TEXT RESULTS:")
print(p_ner.mask_text("Send refund to UPI ID anj123@okhdfcbank or IFSC HDFC0001234."))
