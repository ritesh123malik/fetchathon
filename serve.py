"""Local dashboard. Build frontend first with npm run build --prefix frontend."""
import uvicorn
import os
if __name__=='__main__':
    uvicorn.run('app.api:app',host='127.0.0.1',port=int(os.getenv("RUPEEPILOT_API_PORT", "8080")))
