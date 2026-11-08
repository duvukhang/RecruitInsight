import json
import logging
import time
from uuid import uuid4
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError
from recruitment.adapters.mongo import database
from recruitment.domain.common import AppError
from recruitment.api.auth import router as auth_router
from recruitment.api.system import router as system_router
from recruitment.api.data import router as data_router
from recruitment.api.analytics import router as analytics_router
from recruitment.api.models import router as models_router
from recruitment.api.reports import router as reports_router
from recruitment.api.users import router as users_router
from recruitment.api.profile import router as profile_router

app = FastAPI(title="Recruitment Big Data", version="0.1.0")
app.include_router(auth_router)
app.include_router(system_router)
app.include_router(data_router)
app.include_router(analytics_router)
app.include_router(models_router)
app.include_router(reports_router)
app.include_router(users_router)
app.include_router(profile_router)
logger = logging.getLogger('recruitment.http')
logging.basicConfig(level=logging.INFO, format='%(message)s')


@app.middleware('http')
async def correlation(request, call_next):
    request.state.request_id = str(uuid4())
    started = time.perf_counter()
    response = await call_next(request)
    response.headers['X-Request-ID'] = request.state.request_id
    response.headers['X-Content-Type-Options'] = 'nosniff'
    logger.info(json.dumps({'request_id': request.state.request_id,
                            'method': request.method, 'status': response.status_code,
                            'duration_ms': round((time.perf_counter() - started) * 1000, 2)}))
    return response


@app.exception_handler(AppError)
async def app_error(request, error):
    return JSONResponse(status_code=error.status, content={"error": {
        "code": error.code, "message": error.message, "details": error.details,
        "request_id": getattr(request.state, 'request_id', None)}})


@app.exception_handler(RequestValidationError)
async def validation_error(request, error):
    fields = [{'field': '.'.join(str(x) for x in e['loc']), 'code': e['type']} for e in error.errors()]
    return await app_error(request, AppError('VALIDATION_ERROR', 'Dữ liệu không hợp lệ.', 422, {'fields': fields}))


@app.exception_handler(PyMongoError)
async def database_error(request, error):
    return await app_error(request, AppError('DEPENDENCY_UNAVAILABLE','MongoDB chưa sẵn sàng hoặc truy vấn vượt giới hạn thời gian.',503))


@app.exception_handler(StarletteHTTPException)
async def http_error(request,error):
    return await app_error(request,AppError('NOT_FOUND' if error.status_code==404 else 'HTTP_ERROR',
        'Không tìm thấy API.' if error.status_code==404 else 'Yêu cầu HTTP không hợp lệ.',error.status_code))


@app.exception_handler(Exception)
async def unexpected_error(request,error):
    logger.error(json.dumps({'request_id':getattr(request.state,'request_id',None),'exception_type':type(error).__name__}))
    return await app_error(request,AppError('INTERNAL_ERROR','Không thể xử lý yêu cầu. Vui lòng thử lại hoặc kiểm tra logs.',500))


@app.get('/api/v1/health/live')
def live():
    return {"status": "alive"}


@app.get('/api/v1/health/ready')
def ready():
    try:
        db = database()
        db.command('ping')
        if not db.system_settings.find_one({"_id": "schema", "value": 1}):
            return JSONResponse(status_code=503, content={"status": "schema_not_ready"})
        return {"status": "ready"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "dependency_unavailable"})
