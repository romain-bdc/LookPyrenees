# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.9

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

#RUN --mount=type=secret,id=cop_dataspace_secret /
# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1


WORKDIR /app

COPY . /app

RUN adduser user_lp && chown -R user_lp /app

USER user_lp

ENV PATH="/home/user_lp/.local/bin:${PATH}"
# Install pip requirements
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN python -m pip install -r requirements.txt
RUN pip install .
# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
#CMD ["LookPyrenees", "3seigneurs", "/app/output"]