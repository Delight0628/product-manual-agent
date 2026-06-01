"""数据模型定义"""

from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional
from enum import Enum


class LanguageCode(str, Enum):
    """支持的语言代码"""
    EN = "EN"
    DE = "DE"
    IT = "IT"
    FR = "FR"
    ES = "ES"
    JP = "JP"


class ProductData(BaseModel):
    """亚马逊产品数据"""
    title: str
    bullet_points: List[str] = []
    images: List[str] = []
    price: Optional[str] = None
    asin: Optional[str] = None
    url: Optional[str] = None
    brand: Optional[str] = None


class TranslatedContent(BaseModel):
    """翻译后的内容"""
    language: LanguageCode
    title: str
    bullet_points: List[str]
    installation_steps: Optional[List[str]] = None
    safety_warnings: Optional[List[str]] = None


class ManualRequest(BaseModel):
    """生成说明书请求"""
    url: str
    languages: List[LanguageCode] = Field(
        default=[
            LanguageCode.EN,
            LanguageCode.DE,
            LanguageCode.IT,
            LanguageCode.FR,
            LanguageCode.ES,
            LanguageCode.JP,
        ],
        min_length=1,
    )


class ManualResponse(BaseModel):
    """生成说明书响应"""
    task_id: str
    status: str
    pdf_path: Optional[str] = None
    message: Optional[str] = None


class TaskStatus(BaseModel):
    """任务状态"""
    task_id: str
    status: str  # processing, done, failed
    progress: int = 0
    message: Optional[str] = None
    pdf_path: Optional[str] = None


class MaterialRequest(BaseModel):
    """素材模式请求"""
    prompt: str
    file_ids: List[str] = []
    output_format: str = "pdf"  # pdf / docx
    output_lang: Optional[LanguageCode] = None


class UploadResponse(BaseModel):
    """文件上传响应"""
    file_id: str
    filename: str
    size: int
    content_type: str
