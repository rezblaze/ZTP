#!/bin/sh
#
# /etc/init.d/bmi-builder
# init script for bmi-builder.
#
# BMI BUILDER 

APP_DIR=${PWD}

ver_check(){
  BMI_HOME="/opt/bmi/bmi-builder/"
  VER_FILE="version.text"
  NEW_BMI_BUILDER_VER=$(awk -F= '{print $2}' ${BMI_HOME}${VER_FILE})
  BUILDER_RUNNING=$(systemctl is-active bmi-builder.service)
  re='^[0-9]+$'

  if [[ ! -f ${VER_FILE} ]];then
    echo "${VER_FILE} missing!"
    exit 1
  fi
  
  #Make sure to get current version
  
  if [[ ${BUILDER_RUNNING} = "inactive" ]]; then
    echo "Starting bmi-builder service to get running version."
    start
    builder_running
    if [[ ${BUILDER_RUNNING} = "inactive" ]]; then
      echo "ERROR: BMI BUILDER FAILED TO START!"
      exit 1
    fi
  fi

  PID=$(sudo systemctl status bmi-builder.service|awk '/Main PID:/{print $3}')
  CURRENT_VER=$(strings /proc/${PID}/environ |awk -F= '/BMI_BUILDER_VERSION/{print $2}')
  NEW_MJ=$(echo ${NEW_BMI_BUILDER_VER}|cut -d'.' -f1)
  NEW_MI=$(echo ${NEW_BMI_BUILDER_VER}|cut -d'.' -f2)
  NEW_PA=$(echo ${NEW_BMI_BUILDER_VER}|cut -d'.' -f3)

  CURRENT_MJ=$(echo ${CURRENT_VER}|cut -d'.' -f1)
  CURRENT_MI=$(echo ${CURRENT_VER}|cut -d'.' -f2)
  CURRENT_PA=$(echo ${CURRENT_VER}|cut -d'.' -f3)

  for i in $NEW_MJ $NEW_MI $NEW_PA $CURRENT_MJ $CURRENT_MI $CURRENT_PA
  do
    if ! [[ $i =~ $re ]] ; then
      echo "error: ${i} must be a valid number." >&2; exit 1
    fi
  done

  if [[ ${CURRENT_VER} = ${NEW_BMI_BUILDER_VER} ]]; then
    echo "ABORT: version.text must be updated on github to continue!"
    echo "Running version ${CURRENT_VER} must not match new version ${NEW_BMI_BUILDER_VER}"
    exit 1
  else
    echo "BMI API will start with version ${NEW_BMI_BUILDER_VER}. Old version was ${CURRENT_VER}."
  fi
}

build() {
  echo "==========> building bmi-builder service"
  cd ${APP_DIR}
  python3 -m venv bmi-builder-venv
  . bmi-builder-venv/bin/activate
  pip config --user set global.index https://pypi.example.com:443/artifactory/pypi-virtual/simple
  pip install --upgrade pip
  pip install --upgrade setuptools
  pip install -r requirements.txt --use-deprecated=legacy-resolver
  deactivate
  chmod -R 755 /opt/bmi/bmi-builder
  if [[ ! -f /etc/systemd/system/bmi-builder.service ]]; then
    echo "==========> creating bmi-builder service"
    cat <<EOF >/tmp/bmi-builder.service
[Unit]
Description=BMI Builder service
After=network.target

[Service]
User=serviceuser
Group=servicegroup
WorkingDirectory=/opt/bmi/bmi-builder
Environment="BMI_BUILDER_ENV=stage"
Environment="PYTHONPATH=/opt/bmi/bmi-builder"
EnvironmentFile=/opt/bmi/bmi-builder/version.text
ExecStart=/opt/bmi/bmi-builder/bmi-builder-venv/bin/python app/main.py

[Install]
WantedBy=multi-user.target
EOF
    sudo mv /tmp/bmi-builder.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable bmi-builder.service
    sudo systemctl status bmi-builder.service
fi
}

start() {
  echo "==========> start bmi-builder service"
  sudo systemctl start bmi-builder.service
  sleep 3
  sudo systemctl status bmi-builder.service
}

builder_running() {
  BUILDER_RUNNING=$(sudo systemctl is-active bmi-builder.service)
}

stop() {
  echo "==========> stop bmi-builder service"
  cnt=$(ps -ef | grep /opt/bmi/bmi-builder/bmi-builder-venv/bin/python | grep -vc grep)
  if [[ ${cnt} -gt 1 ]]; then
    echo "Builer is running with ${cnt} processes!"
    echo "builder may have running build please check! exit"
    exit 1
  else
    echo "builder is safe to stop!"
  fi
  sudo systemctl stop bmi-builder.service
  sudo systemctl status bmi-builder.service
}

restart() {
  echo "==========> restart bmi-builder service"
  sudo systemctl restart bmi-builder.service
  sudo systemctl status bmi-builder.service
}

status() {
  echo "==========> status bmi-builder service"
  sudo systemctl status bmi-builder.service
}

update(){
  echo "==========> update bmi-builder service"
  git stash
  git pull
  ver_check
  stop
  if [[ ! -d /var/log/bmi-builder ]]; then
    sudo mkdir /var/log/bmi-builder
    sudo chown serviceuser:servicegroup /var/log/bmi-builder
  fi
  echo "==========> move all logs to /var/log/bmi-builder"
  mv log/* /var/log/bmi-builder/
  # git stash
  # git pull
  build
  start
}


### mac
mac_build(){
    cd ${APP_DIR}
    python3 -m venv bmi-builder-venv
    . bmi-builder-venv/bin/activate
    pip config --user set global.index https://pypi.example.com:443/artifactory/pypi-virtual/simple
    pip install --upgrade pip
    pip install --upgrade setuptools
    pip install -r requirements.txt --use-deprecated=legacy-resolver
    deactivate
    chmod 755 log
}

mac_start() {
  cd ${APP_DIR}
  . bmi-builder-venv/bin/activate
  export PYTHONWARNINGS="ignore:Unverified HTTPS request"
  export BMI_BUILDER_ENV="local"
  export PYTHONPATH="${APP_DIR}"
  echo "cleaning up logs"
  rm -rf ${APP_DIR}/log/*.*
  echo "starting bmi-builder"
  python3 ${APP_DIR}/app/main.py &
  PROCESS_ID=$!
  echo $PROCESS_ID > ${APP_DIR}/bmi_builder.pid
  cat ${APP_DIR}/bmi_builder.pid
}

mac_stop() {
  cd ${APP_DIR}
  echo Stopping BMI builder...
  kill -2 `cat bmi_builder.pid`
}

mac_restart() {
    mac_stop
    sleep 1
    mac_start
}

mac_status() {
  echo BMI builder status:
  ps -ef | grep `cat bmi_builder.pid`
  RETVAL=$?
}

mac_update() {
  mac_stop
  git pull
  mac_start
}

###
### main() 
###

system=$(uname)
echo "==========> [$0 - lazy developer script]"
echo "Platform: ${system}"
if [[ ${system} == "Darwin" ]]; then
  case "$1" in
    build) mac_build ;;
    start) mac_start ;;
    stop) mac_stop ;;
    restart) mac_restart ;;
    status) mac_status ;;
    update) mac_update ;;   
    *)  echo "Usage: $0 {build|start|stop|restart|status|update}"
        exit 1 ;;
  esac  
fi
if [[ ${system} == "Linux" ]]; then
  case "$1" in
    build) build ;;
    start) start ;;
    stop) stop ;;
    restart) restart ;;
    status) status ;;
    update) update ;;
    *)  echo "Usage: $0 {build|start|stop|restart|status|update}"
        exit 1 ;;
  esac
fi