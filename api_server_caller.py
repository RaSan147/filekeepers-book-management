import API
from API import migrate as api_migrate

MODE = "PROD"  # Change to "PROD" for production

if __name__ == "__main__":
	# Run migrations
	import asyncio
	asyncio.run(api_migrate.migrate())

if __name__ == "__main__" and MODE == "PROD":
	import uvicorn
	uvicorn.run(
		API.app, host=API.API_HOST, port=API.API_PORT, 
	)

if __name__ == "__main__" and MODE == "DEV":
	import subprocess
	import sys
	import os

	def run_fastapi_dev(app_path="main:app", port=8080, host="0.0.0.0", reload=True):
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

	run_fastapi_dev("API:app", port=8080)
