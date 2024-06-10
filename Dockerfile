# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.9

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

WORKDIR /LookPyrenees

COPY . /LookPyrenees

RUN groupadd -r user_lp
RUN useradd -r -g user_lp user_lp 

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
RUN python -m pip install --upgrade pip
RUN python -m pip install -r requirements.txt
RUN pip install .

USER user_lp

ENTRYPOINT ["python3", "src/LookPyrenees/cli.py"]
# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD ["-b", "pyrenees_images"]