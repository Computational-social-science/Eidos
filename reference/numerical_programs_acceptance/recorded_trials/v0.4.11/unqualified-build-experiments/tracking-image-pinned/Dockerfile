FROM sha256:8f137816f3f718fbc84d0e37ff07b3b25690d981ed0658a27a88977a58ee93ec

COPY eidos-0.4.11-py3-none-any.whl /tmp/
RUN ["/opt/tracking/bin/python", "-I", "-m", "pip", "install", "--no-index", "/tmp/eidos-0.4.11-py3-none-any.whl"]
RUN ["/opt/tracking/bin/python", "-I", "-m", "pip", "check"]
