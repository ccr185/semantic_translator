FROM minizinc/minizinc

WORKDIR /usr/src/app

RUN apt-get -y upgrade

RUN apt-get update && apt-get upgrade -y

RUN apt-get install software-properties-common python3 python3-pip nginx -y

RUN apt-add-repository ppa:swi-prolog/stable

RUN apt-get update

RUN apt-get install swi-prolog -y

RUN apt-get install python3.12-venv -y

RUN python3 -m venv venv

ENV PATH="./venv/bin:$PATH"

RUN pip install flask minizinc swiplserver pydantic==1.10.2 networkx pyhumps textx z3-solver

RUN echo $(pip show textx)

RUN pip install gunicorn

COPY . .

EXPOSE 5001
CMD ["./venv/bin/gunicorn", "--bind=0.0.0.0:5001", "--workers=16", "app:app" , "--timeout 0" ]
#CMD ["flask", "run", "--port=5001", "--host=0.0.0.0"]