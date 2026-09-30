[![CodeQL](https://github.example.com/example-org/ztp-service/actions/workflows/codeql.yml/badge.svg)](https://github.example.com/example-org/ztp-service/actions/workflows/codeql.yml)

# bmi-service
Bare Metal Imaging API

## Local Build
### Kafka
Setup kafka and create necessary topics.

### Python Environment
Ensure python 3.8 is installed

Create virtual environment:
```bash
cd bmi-service
bash ansible/bmi_api.sh build
bash ansible/bmi_api.sh start
```

### Access Swagger docs
http://localhost:8080/docs

