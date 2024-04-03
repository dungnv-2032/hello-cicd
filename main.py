import os
import urllib.request

from flask import Flask

app = Flask(__name__)


@app.route("/hello-world")
def hello_world():
    return "hello-world"


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))