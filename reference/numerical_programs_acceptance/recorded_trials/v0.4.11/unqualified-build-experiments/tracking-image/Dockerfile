FROM eidos-tracking-acceptance:v410
COPY eidos-0.4.11-py3-none-any.whl /tmp/
RUN ["/opt/tracking/bin/python", "-I", "-m", "pip", "install", "--no-index", "/tmp/eidos-0.4.11-py3-none-any.whl"]
RUN ["/opt/tracking/bin/python", "-I", "-m", "pip", "check"]
