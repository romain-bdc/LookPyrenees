# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:alpine

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1


RUN apk update && apk add --no-cache gdal-dev \
python3-dev \
py3-pip \
build-base \
musl-dev \
linux-headers \
geos-dev \
proj-dev \
proj-util \
libc-dev \
gcc \
g++ \
jpeg-dev \
zlib-dev \
freetype-dev \
lcms2-dev \
openjpeg-dev \
tiff-dev \
tk-dev \
tcl-dev \
harfbuzz-dev \
fribidi-dev \
libimagequant-dev \
libxcb-dev \
libpng-dev \
gdal-driver-jp2openjpeg

WORKDIR /LookPyrenees

COPY . /LookPyrenees

RUN addgroup -S user_lp
RUN adduser -S -g user_lp user_lp 

RUN mkdir -p /home/user_lp/.config /home/user_lp/.cache /LookPyrenees/output
RUN chown -R user_lp:user_lp /home/user_lp /LookPyrenees

# Set environment variables for Matplotlib and Fontconfig
ENV MPLCONFIGDIR=/LookPyrenees/output/.matplotlib
ENV XDG_CACHE_HOME=/LookPyrenees/output/.cache

# Ensure directories exist and have correct permissions
RUN mkdir -p $MPLCONFIGDIR $XDG_CACHE_HOME
RUN chown -R user_lp:user_lp $MPLCONFIGDIR $XDG_CACHE_HOME

# Install pip requirements
# COPY requirements.txt /LookPyrenees/
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install -r requirements.txt
RUN pip install .

USER user_lp

ENTRYPOINT ["python3", "src/LookPyrenees/cli.py"]
# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
# CMD ["-b", "pyrenees_images"]