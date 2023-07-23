import string
from flask import Flask, jsonify, request
import asyncio
from threading import Thread
import random
from SiaScraper.SiaRequests import SiaScraper

app = Flask(__name__)

@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"

@app.route("/api/v1/startProcess", methods=["POST"])
def get_data():
	# Sync call to get data
	body = request.get_json()
	careerCode = body['careerCode']
	courseIndex = body['courseIndex']
	randomName = ''.join(random.choice(string.ascii_letters) for i in range(10))
	thread = Thread(target=asyncio.run, args=(get_data_async(careerCode, courseIndex, randomName),))
	thread.daemon = True
	thread.start()
	return jsonify({"message": "Data will be available soon", "filename": f"{randomName}"})

@app.route("/api/v1/status/<filename>")
def get_data_status(filename):
	# Check if data is available
	try:
		with open(f"{filename}.txt", "r") as f:
			lines = f.readlines()
			return jsonify({"message": "Data available"})
	except:
		return jsonify({"message": "Data not available yet"})
	
@app.route("/api/v1/getData/", defaults={'filename': None})
@app.route("/api/v1/getData/<filename>")
def get_data_file(filename):
	# Get data from file
	try:
		with open(f"{filename}.txt", "r") as f:
			lines = f.readlines()
			return jsonify({"message": lines})
	except:
		return jsonify({"message": "Data not available yet"})

async def get_data_async(careerCode: string, courseIndex: int, randomName: string):
	# Async call to get data with asyncio
	data = SiaScraper().createSession().setCareer(careerCode).getCourseInfo(courseIndex)['nombreAsignatura']
	print("Async call done")
	lines = data.split("\n")
	with open(f"{randomName}.txt", "w") as f:
		f.writelines(data)
	return "data"

if __name__ == "__main__":
	app.run(host="localhost", port=5000, debug=True)