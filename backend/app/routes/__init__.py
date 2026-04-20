from app.routes.deals import router as deals_router
from app.routes.chat import router as chat_router
from app.routes.admin import router as admin_router
from app.routes.admin_analytics import router as admin_analytics_router
from app.routes.export import router as export_router
from app.routes.billing import router as billing_router
from app.routes.seo import router as seo_router
from app.routes.marketing import router as marketing_router

__all__ = [
    "deals_router",
    "chat_router",
    "admin_router",
    "admin_analytics_router",
    "export_router",
    "billing_router",
    "seo_router",
    "marketing_router",
]
