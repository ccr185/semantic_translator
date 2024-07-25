# Introduction
This repository contains the version of the Extended PLIEADES Architecture's Prototype as submitted to the conference.
It contains a fully working prototype capable of providing automated reasoning services that are agnostic to both the
specific Variability Modeling Language given as input and the Inference Engine (solver) used to perform a given
reasoning task on the Variability Model. The paper focuses on extending both the architecture and prototype to
deal with textual variability modeling languages. As such, all the data here contained is of this nature.

This version reflects the status of the repository at the time of submission.

Added to this zip file is the data used for experimentation in the benchmark folder and the script used to get the exact data used in the paper.

The data consists of a large collection of Variability Models in the UVL textual format.

# Instructions to run the Extended PLEIADES Architecture Prototype and Benchmarks

N.B. The prototype has *only* been tested to run reliably on linux. The recommended platform-independent installation is through Docker.

To construct the docker image you will need the following command:
```
$ docker build -t pleiades .
```

Next, run the docker container with the following command:
```
$ docker run -it -p 5000:5001 pleiades 
```
If you have issues with memory usage, you can try the following command. Do keep in mind that this does require appropriate ulimits on your linux base.
```
$ docker run -it -p 5000:5001 --ulimit stack=8192000000:8192000000 --memory=8g pleiades
```

Once you have a running container on port 5001, you can run the benchmark script to regenerate all the data used for the article. It is located in the benchmark/run_bench folder.

NOTE: Depending on your machine and its characteristics, you may want to reduce the number of requests done in parallel to reduce memory/cpu consumption.
This is especially important if you want to avoid any instability on your machine at the cost of higher runtime for the benchmarks.
To tune this you must modify benchmark/run_bench/run_test4.sh and change the n parameter on line 7 to something smaller. Generally a safe bet is the
2*maximum number of cores you have available or even just 1*your number of cores. It is prudent to change the "--workers=16" part of line 26 of the Dockerfile to this number as well.

You can do the following to run it.
```
$ cd benchmark/run_bench
# you may need to make the script runnable
$ chmod +x ./run_test4.sh
# This runs it for the z3 solver
$ ./run_test4.sh z3
# This is for SWI
$ ./run_test4.sh swi
# This is for MiniZinc
$ ./run_test4.sh minizinc
```

This will generate a file named output_detailed_<solver>.csv which will have all the data inside.

We have kept all 15 original runs in the benchmark folder.
