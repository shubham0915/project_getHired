import pandas as pd
from sdv.metadata import SingleTableMetadata
from sdv.single_table import GaussianCopulaSynthesizer
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_synthetic_data(masked_data_path="masked_fintech_data.csv", output_path="synthetic_fintech_data.csv", num_rows=1000):
    logger.info(f"Loading masked data from {masked_data_path}")
    df = pd.read_csv(masked_data_path)
    
    # SDV requires us to define metadata
    logger.info("Detecting metadata from data...")
    metadata = SingleTableMetadata()
    metadata.detect_from_dataframe(df)
    
    # We can explicitly set primary keys or PII if needed, 
    # but since this data is ALREADY masked, we just want to synthesize the same distributions.
    if 'Transaction_ID' in df.columns:
        metadata.update_column(column_name='Transaction_ID', sdtype='id')
        metadata.set_primary_key(column_name='Transaction_ID')
        
    logger.info("Training Gaussian Copula Synthesizer (Fast & Tabular)...")
    synthesizer = GaussianCopulaSynthesizer(metadata)
    synthesizer.fit(df)
    
    logger.info(f"Generating {num_rows} synthetic rows...")
    synthetic_data = synthesizer.sample(num_rows=num_rows)
    
    synthetic_data.to_csv(output_path, index=False)
    logger.info(f"Saved synthetic data to {output_path}")
    return synthetic_data

if __name__ == "__main__":
    generate_synthetic_data(num_rows=200)
