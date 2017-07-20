FROM friend1ws/annot_utils 
MAINTAINER Yuichi Shiraishi <friend1ws@gmail.com> 

WORKDIR /usr/local/bin

RUN pip install --upgrade pip
RUN pip install pysam

RUN wget https://github.com/friend1ws/intron_retention_utils/archive/v0.3.0.tar.gz && \
    tar xzvf v0.3.0.tar.gz && \
    cd intron_retention_utils-0.3.0 && \
    python setup.py build install

WORKDIR /data

ENTRYPOINT ["/usr/local/bin/intron_retention_utils"]
CMD ["--help"]

