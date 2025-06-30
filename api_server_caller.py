from API import main as api_main
from API import migrate as api_migrate

if __name__ == "__main__":
	# Run migrations
	import asyncio
	asyncio.run(api_migrate.migrate())

if __name__ == "PROD__main__":
	import uvicorn
	uvicorn.run(
		api_main.app, host=api_main.API_HOST, port=api_main.API_PORT, 
	)

if __name__ == "__main__":#DEV
	import subprocess
	import sys
	import os

	def run_fastapi_dev(app_path="main:app", port=8000, host="127.0.0.1", reload=True):
		command = [
			sys.executable, "-m", "uvicorn", app_path,
			"--host", host,
			"--port", str(port),
		]
		
		if reload:
			command.append("--reload")

		# Optional: set env variables like development settings
		env = os.environ.copy()
		env["ENV"] = "development"

		print(f"Running: {' '.join(command)}")
		subprocess.run(command, env=env)

	# Change "main:app" if your FastAPI app is in a different file or named differently
	run_fastapi_dev("API:app", port=8000)
