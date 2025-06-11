FROM python:3.11-slim


RUN apt update && apt install -y git cmake build-essential libeigen3-dev libopencv-dev libceres-dev tmux wget curl openssl zip make autoconf automake pkg-config libudev-dev libusb-1.0-0-dev

COPY install_ttyd.sh .

RUN ./install_ttyd.sh

# Install VINS-Fusion
RUN git clone --branch apm_wiki https://github.com/chobitsfan/VINS-Fusion.git
RUN cd VINS-Fusion/vins_estimator && cmake . && make -j$(nproc)

#install depthai-core
# Todo: lock version. tested with 2.25.0
RUN git clone --branch v2.30.0 https://github.com/luxonis/depthai-core
RUN cd depthai-core && git submodule update --init --recursive
RUN cd depthai-core && cmake -S. -Bbuild
RUN cd depthai-core && cmake --build build --parallel $(nproc) --target install


# Install oak_d_vins_cpp
RUN git clone --branch apm_wiki https://github.com/williangalvani/oak_d_vins_cpp.git
RUN cd oak_d_vins_cpp && cmake -D'depthai_DIR=../depthai-core/build/install/lib/cmake/depthai' .
RUN cd oak_d_vins_cpp && make -j$(nproc)

#install mavlink-udp-proxy
RUN git clone --branch apm_wiki https://github.com/chobitsfan/mavlink-udp-proxy.git
RUN cd mavlink-udp-proxy && git submodule update --init --recursive && ./build_it

COPY entrypoint.sh .

COPY tmux.conf /etc/tmux.conf

RUN apt install -y nginx

COPY nginx.conf /etc/nginx/nginx.conf

COPY register_service.json /app/register_service.json

RUN pip install requests eclipse-zenoh

COPY mavlink2restForwarder.py .

LABEL version="0.0.1"

ARG IMAGE_NAME=OAKD_VINS

LABEL permissions='\
{\
  "ExposedPorts": {\
    "8000/tcp": {}\
  },\
  "HostConfig": {\
    "Binds":["/dev/bus/usb:/dev/bus/usb"],\
    "DeviceCgroupRules": [\
      "c 189:* rmw"\
    ],\
    "ExtraHosts": ["host.docker.internal:host-gateway"],\
    "PortBindings": {\
      "8000/tcp": [\
        {\
          "HostPort": ""\
        }\
      ]\
    }\
  }\
}'

LABEL authors='[\
    {\
        "name": "Willian Galvani",\
        "email": "willian@bluerobotics.com"\
    }\
]'

LABEL company='{\
        "about": "",\
        "name": "Blue Robotics",\
        "email": "support@bluerobotics.com"\
    }'
LABEL type="device-integration"

LABEL readme='https://raw.githubusercontent.com/williangalvani/Blueos-oakd-vins/{tag}/README.md'
LABEL links='{\
        "source": "https://github.com/williangalvani/Blueos-oakd-vins"\
    }'
LABEL requirements="core >= 1.1"
RUN chmod +x entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
