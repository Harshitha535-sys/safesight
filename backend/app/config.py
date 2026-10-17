from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    app_name: str = "SafeSight AI"
    version: str = "0.1.0"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Detection model (YOLOX-nano, COCO-pretrained, Apache-2.0)
    model_path: Path = BACKEND_DIR / "models" / "yolox_nano.onnx"
    model_url: str = (
        "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_nano.onnx"
    )
    model_sha256: str = "c789161ed43c8269fcd4e67c67eeeb4e80c622da2eb296a20bc6007bd18a0b7d"
    conf_threshold: float = 0.4

    # Storage / limits
    data_dir: Path = BACKEND_DIR / "data"
    max_upload_mb: int = 200

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
