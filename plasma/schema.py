REQUIRED_METADATA = ["id", "source_sha256", "split", "created_by", "review_status", "weight"]
VALID_SPLITS = ["train", "val", "test", "inference"]
DEFAULT_CREATED_BY = "sovereign_pipeline"
DEFAULT_REVIEW_STATUS = "pending"
ENTROPY_CAP = 0.20  # from IRR spec — maximum entropy on generated patterns
