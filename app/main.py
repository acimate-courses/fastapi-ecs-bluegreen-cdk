from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World for blue green deployment"}

@app.get("/health")
def health():
    return {"status": "ok"}
