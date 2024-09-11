# This Dockerfile is used to build an headles vnc image based on Debian

FROM debian:11


## Connection ports for controlling the UI:
# VNC port:5901
# noVNC webport, connect via http://IP:6901/?password=vncpassword
ENV DISPLAY=:1 \
    VNC_PORT=5901 \
    NO_VNC_PORT=6901
EXPOSE $VNC_PORT $NO_VNC_PORT

### Envrionment config
ENV HOME=/headless \
    TERM=xterm \
    STARTUPDIR=/dockerstartup \
    INST_SCRIPTS=/headless/install \
    NO_VNC_HOME=/headless/noVNC \
    DEBIAN_FRONTEND=noninteractive \
    VNC_COL_DEPTH=24 \
    VNC_RESOLUTION=1280x1024 \
    VNC_PW=vncpassword \
    VNC_VIEW_ONLY=false \
    VNC_PASSWORDLESS=true \
    USER=headless
WORKDIR $HOME

### Add all install scripts for further steps
ADD ./src/common/install/ $INST_SCRIPTS/
ADD ./src/debian/install/ $INST_SCRIPTS/

### Install some common tools
RUN $INST_SCRIPTS/tools.sh
ENV LANG='en_US.UTF-8' LANGUAGE='en_US:en' LC_ALL='en_US.UTF-8'

### Install custom fonts
RUN $INST_SCRIPTS/install_custom_fonts.sh

### Install xvnc-server & noVNC - HTML5 based VNC viewer
RUN $INST_SCRIPTS/tigervnc.sh
RUN $INST_SCRIPTS/no_vnc.sh

# Define volumes for Browser profiles
VOLUME /browserProf

### Install firefox and chrome browser
RUN $INST_SCRIPTS/openkiosk.sh

# Copy Pre-configured OpenKiosk Profile
ADD ./src/common/kioskProf/ $HOME/broProf
ADD ./src/prefs.js $HOME/prefs.js

# Install Python and Flask
RUN apt-get update && apt-get install -y python3 python3-pip
RUN pip3 install flask gunicorn 
RUN pip install psutil
RUN pip install waitress

# Add Gunicorn config file
#ADD ./src/gunicorn_config.py $STARTUPDIR/gunicorn_config.py


# Add the Flask application
ADD ./src/app.py $STARTUPDIR/app.py
#ADD ./src/common/static/ $HOME/static/

### Install xfce UI
RUN $INST_SCRIPTS/xfce_ui.sh
ADD ./src/common/xfce/ $HOME/

### configure startup
RUN $INST_SCRIPTS/libnss_wrapper.sh
ADD ./src/common/scripts $STARTUPDIR
RUN $INST_SCRIPTS/set_user_permission.sh $STARTUPDIR $HOME

USER 1000

#ENTRYPOINT ["/dockerstartup/vnc_startup.sh"]
#CMD ["--wait"]

ENTRYPOINT ["python3", "/dockerstartup/app.py"]

ENV PYTHONPATH $STARTUPDIR

#ENTRYPOINT ["gunicorn", "--config", "/dockerstartup/gunicorn_config.py", "app:app"]
