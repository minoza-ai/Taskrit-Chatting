from fastapi.responses import FileResponse


def read_index_service():
    return FileResponse("index.html")