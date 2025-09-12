from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World for blue green deployment date= 12-Aug-2025"}

@app.get("/health")
def health():
    return {"status": "ok"}
