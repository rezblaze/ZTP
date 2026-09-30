#!/bin/bash
#
# /etc/init.d/bmi-service
# init script for bmi-service.
#
# Author: chirag Patel

APP_DIR=${PWD}
HOSTNAME=$(hostname)

ver_check() {
    BMI_HOME="/opt/bmi/bmi-service/"
    VER_FILE="version.text"
    NEW_BMI_API_VER=$(awk -F= '{print $2}' ${BMI_HOME}${VER_FILE})
    API_RUNNING=$(systemctl is-active bmi-service.service)
    re='^[0-9]+$'
    
    if [[ ! -f ${VER_FILE} ]];then
        echo "${VER_FILE} missing!"
        exit 1
    fi
    
    #Make sure to get current version
    
    if [[ ${API_RUNNING} = "inactive" ]]; then
        echo "Starting bmi-service service to get running version."
        start
        api_running
        if [[ ${API_RUNNING} = "inactive" ]]; then
            echo "ERROR: BMI API FAILED TO START!"
            exit 1
        fi
    fi
    
    PID=$(sudo systemctl status bmi-service.service|awk '/Main PID:/{print $3}')
    CURRENT_VER=$(strings /proc/${PID}/environ |awk -F= '/BMI_API_VERSION/{print $2}')
    NEW_MJ=$(echo ${NEW_BMI_API_VER}|cut -d'.' -f1)
    NEW_MI=$(echo ${NEW_BMI_API_VER}|cut -d'.' -f2)
    NEW_PA=$(echo ${NEW_BMI_API_VER}|cut -d'.' -f3)
    
    CURRENT_MJ=$(echo ${CURRENT_VER}|cut -d'.' -f1)
    CURRENT_MI=$(echo ${CURRENT_VER}|cut -d'.' -f2)
    CURRENT_PA=$(echo ${CURRENT_VER}|cut -d'.' -f3)
    
    for i in $NEW_MJ $NEW_MI $NEW_PA $CURRENT_MJ $CURRENT_MI $CURRENT_PA
    do
        if ! [[ $i =~ $re ]] ; then
            echo "error: ${i} must be a valid number." >&2; exit 1
        fi
    done
    
    if [[ ${CURRENT_VER} = ${NEW_BMI_API_VER} ]]; then
        echo "ABORT: version.text must be updated on github to continue!"
        echo "Running version ${CURRENT_VER} must not match new version ${NEW_BMI_API_VER}"
        exit 1
    else
        echo "BMI API will start with version ${NEW_BMI_API_VER}. Old version was ${CURRENT_VER}."
    fi
}

###
### Linux vm environment
###

create_service() {
    echo "==========> creating bmi-service systemd service"
    cat <<EOF >/tmp/bmi-service.service
[Unit]
Description=BMI API service
After=bmi-builder.service

[Service]
User=serviceuser
Group=servicegroup
WorkingDirectory=/opt/bmi/bmi-service
Environment="BMI_API_ENV=${BMI_ENV}"
Environment="PYTHONPATH=/opt/bmi/bmi-service"
EnvironmentFile=/opt/bmi/bmi-service/version.text
ExecStart=/opt/bmi/bmi-service/bmi-service-venv/bin/python app/main.py

[Install]
WantedBy=multi-user.target
EOF
    sudo mv /tmp/bmi-service.service /etc/systemd/system/bmi-service.service
    sudo systemctl daemon-reload
    sudo systemctl enable bmi-service.service
    sudo systemctl status bmi-service.service
}

build() {
    echo "==========> building bmi-service service"
    cd ${APP_DIR}
    python -m venv bmi-service-venv
    . bmi-service-venv/bin/activate
    pip config --user set global.index https://pypi.example.com:443/artifactory/pypi-virtual/simple
    pip install --upgrade pip
    pip install --upgrade setuptools
    pip install -r requirements.txt
    deactivate
    chmod 755 log
    
    if [[ -f /etc/systemd/system/bmi-service.service ]]; then
        ENV=$(grep BMI_API_ENV /etc/systemd/system/bmi-service.service | awk -F"\"" '{print $2}' | awk -F"=" '{print $2}')
        if [[ ${ENV} != ${BMI_ENV} ]]; then
            echo "Fixing environment variable"
            sudo rm -rf /etc/systemd/system/bmi-service.service
            create_service
        fi
    else
        create_service
    fi
}

api_running() {
    API_RUNNING=$(sudo systemctl is-active bmi-service.service)
}

start() {
    echo "==========> start bmi-service service"
    sudo systemctl start bmi-service.service
    sudo systemctl status bmi-service.service
}

stop() {
    echo "==========> stop bmi-service service"
    sudo systemctl stop bmi-service.service -f
    sudo systemctl status bmi-service.service
}

restart() {
    echo "==========> restart bmi-service service"
    sudo systemctl restart bmi-service.service
    sudo systemctl status bmi-service.service
}

status() {
    echo "==========> status bmi-service service"
    sudo systemctl status bmi-service.service
}

update() {
    echo "==========> update bmi-builder service"
    git stash
    git pull
    ver_check
    stop
    if [[ ! -d /var/log/bmi-service ]]; then
        sudo mkdir /var/log/bmi-service
        sudo chown serviceuser:servicegroup /var/log/bmi-service
    fi
    echo "==========> move all logs to /var/log/bmi-service"
    mv log/* /var/log/bmi-service/
    build
    start
}

###
### Mac local development environemnt
###

mac_build() {
    cd ${APP_DIR}
    python -m venv bmi-service-venv
    . bmi-service-venv/bin/activate
    pip config --user set global.index https://repo1.example.com:443/artifactory/pypi-virtual/simple
    pip install --upgrade pip
    pip install --upgrade setuptools
    pip install -r requirements.txt --use-deprecated=legacy-resolver
    deactivate
}

mac_start() {
    cnt=$(ps -ef | grep -c "bmi-service/app/main.py")
    if [[ $cnt -gt 1 ]]; then
        echo "FAIL: BMI API already running so run stop or kill the process"
        exit
    fi
    cd ${APP_DIR}
    . bmi-service-venv/bin/activate
    export PYTHONWARNINGS="ignore:Unverified HTTPS request"
    export BMI_API_ENV="${BMI_ENV}"
    export PYTHONPATH="${APP_DIR}"

    if [[ -f ~/.chavi ]]; then
        echo "==========> sourcing chavi"
        source ~/.chavi
    fi
    echo "==========> cleaning up logs"
    rm -rf ${APP_DIR}/log/*.*
    echo "==========> starting bmi-service"
    python ${APP_DIR}/app/main.py &
    PROCESS_ID=$!
    echo $PROCESS_ID > ${APP_DIR}/bmi_api.pid
    cat ${APP_DIR}/bmi_api.pid
}

mac_stop() {
    cd ${APP_DIR}
    echo Stopping BMI API...
    kill `cat bmi_api.pid`
}

mac_restart() {
    mac_stop
    sleep 1
    mac_start
}

mac_status() {
    echo BMI API status:
    ps -ef | grep `cat bmi_api.pid`
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
echo "hostname: ${HOSTNAME}"

case ${HOSTNAME} in
    lab-bmi-stage-01)
        echo "This is development environment"
        BMI_ENV="dev"
    ;;
    # lab-bmi-legacy-02)
    #     echo "This is stage environment"
    #     BMI_ENV="stage"
    # ;;
    lab-bmi-dev-01)
        echo "This is stage environment"
        BMI_ENV="stage"
    ;;
    # lab-bmi-legacy-01)
    #     echo "This is production environment"
    #     BMI_ENV="prod"
    # ;;
    lab-bmi-prod-01)
        echo "This is production environment"
        BMI_ENV="prod"
    ;;
    *)
        echo "Warning: unknown environment so setting up as local"
        BMI_ENV="local"
    ;;
esac

if [[ ${system} == "Darwin" ]]; then
    case "$1" in
        build) mac_build ;;
        start) mac_start ;;
        stop) mac_stop ;;
        restart) mac_restart ;;
        status) mac_status ;;
        update) mac_update ;;
        *)  echo "==========> Usage: $0 {build|start|stop|restart|status|update}"
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
        *)  echo "==========> Usage: $0 {build|start|stop|restart|status|update}"
        exit 1 ;;
    esac
fi
