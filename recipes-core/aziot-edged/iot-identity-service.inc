# IoT Identity Service git dependencies
# These are the IIS library crates needed by IoT Edge recipes
# IIS_SRCREV must be defined by the version-specific .inc file

SRC_URI += " \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-cert-client-async;destsuffix=cert/aziot-cert-client-async;subpath=cert/aziot-cert-client-async \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-cert-common-http;destsuffix=cert/aziot-cert-common-http;subpath=cert/aziot-cert-common-http \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-certd-config;destsuffix=cert/aziot-certd-config;subpath=cert/aziot-certd-config \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-identity-client-async;destsuffix=identity/aziot-identity-client-async;subpath=identity/aziot-identity-client-async \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-identity-common-http;destsuffix=identity/aziot-identity-common-http;subpath=identity/aziot-identity-common-http \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-identity-common;destsuffix=identity/aziot-identity-common;subpath=identity/aziot-identity-common \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-identityd-config;destsuffix=identity/aziot-identityd-config;subpath=identity/aziot-identityd-config \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-key-client-async;destsuffix=key/aziot-key-client-async;subpath=key/aziot-key-client-async \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-key-client;destsuffix=key/aziot-key-client;subpath=key/aziot-key-client \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-key-common-http;destsuffix=key/aziot-key-common-http;subpath=key/aziot-key-common-http \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-key-common;destsuffix=key/aziot-key-common;subpath=key/aziot-key-common \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-key-openssl-engine;destsuffix=key/aziot-key-openssl-engine;subpath=key/aziot-key-openssl-engine \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-keyd-config;destsuffix=key/aziot-keyd-config;subpath=key/aziot-keyd-config \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-keys-common;destsuffix=key/aziot-keys-common;subpath=key/aziot-keys-common \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziot-tpmd-config;destsuffix=tpm/aziot-tpmd-config;subpath=tpm/aziot-tpmd-config \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=aziotctl-common;destsuffix=aziotctl/aziotctl-common;subpath=aziotctl/aziotctl-common \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=cert-renewal;destsuffix=cert/cert-renewal;subpath=cert/cert-renewal \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=config-common;destsuffix=config-common;subpath=config-common \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=http-common;destsuffix=http-common;subpath=http-common \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=logger;destsuffix=logger;subpath=logger \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=openssl-build;destsuffix=openssl-build;subpath=openssl-build \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=openssl-sys2;destsuffix=openssl-sys2;subpath=openssl-sys2 \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=openssl2;destsuffix=openssl2;subpath=openssl2 \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=pkcs11-sys;destsuffix=pkcs11/pkcs11-sys;subpath=pkcs11/pkcs11-sys \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=pkcs11;destsuffix=pkcs11/pkcs11;subpath=pkcs11/pkcs11 \
    git://github.com/Azure/iot-identity-service;protocol=https;nobranch=1;name=test-common;destsuffix=test-common;subpath=test-common \
"

SRCREV_FORMAT .= "_aziot-cert-client-async"
SRCREV_aziot-cert-client-async = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/cert/aziot-cert-client-async"
SRCREV_FORMAT .= "_aziot-cert-common-http"
SRCREV_aziot-cert-common-http = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/cert/aziot-cert-common-http"
SRCREV_FORMAT .= "_aziot-certd-config"
SRCREV_aziot-certd-config = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/cert/aziot-certd-config"
SRCREV_FORMAT .= "_aziot-identity-client-async"
SRCREV_aziot-identity-client-async = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/identity/aziot-identity-client-async"
SRCREV_FORMAT .= "_aziot-identity-common"
SRCREV_aziot-identity-common = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/identity/aziot-identity-common"
SRCREV_FORMAT .= "_aziot-identity-common-http"
SRCREV_aziot-identity-common-http = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/identity/aziot-identity-common-http"
SRCREV_FORMAT .= "_aziot-identityd-config"
SRCREV_aziot-identityd-config = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/identity/aziot-identityd-config"
SRCREV_FORMAT .= "_aziot-key-client"
SRCREV_aziot-key-client = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/key/aziot-key-client"
SRCREV_FORMAT .= "_aziot-key-client-async"
SRCREV_aziot-key-client-async = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/key/aziot-key-client-async"
SRCREV_FORMAT .= "_aziot-key-common"
SRCREV_aziot-key-common = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/key/aziot-key-common"
SRCREV_FORMAT .= "_aziot-key-common-http"
SRCREV_aziot-key-common-http = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/key/aziot-key-common-http"
SRCREV_FORMAT .= "_aziot-key-openssl-engine"
SRCREV_aziot-key-openssl-engine = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/key/aziot-key-openssl-engine"
SRCREV_FORMAT .= "_aziot-keyd-config"
SRCREV_aziot-keyd-config = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/key/aziot-keyd-config"
SRCREV_FORMAT .= "_aziot-keys-common"
SRCREV_aziot-keys-common = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/key/aziot-keys-common"
SRCREV_FORMAT .= "_aziot-tpmd-config"
SRCREV_aziot-tpmd-config = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/tpm/aziot-tpmd-config"
SRCREV_FORMAT .= "_aziotctl-common"
SRCREV_aziotctl-common = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/aziotctl/aziotctl-common"
SRCREV_FORMAT .= "_cert-renewal"
SRCREV_cert-renewal = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/cert/cert-renewal"
SRCREV_FORMAT .= "_config-common"
SRCREV_config-common = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/config-common"
SRCREV_FORMAT .= "_http-common"
SRCREV_http-common = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/http-common"
SRCREV_FORMAT .= "_logger"
SRCREV_logger = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/logger"
SRCREV_FORMAT .= "_openssl-build"
SRCREV_openssl-build = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/openssl-build"
SRCREV_FORMAT .= "_openssl-sys2"
SRCREV_openssl-sys2 = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/openssl-sys2"
SRCREV_FORMAT .= "_openssl2"
SRCREV_openssl2 = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/openssl2"
SRCREV_FORMAT .= "_pkcs11"
SRCREV_pkcs11 = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/pkcs11/pkcs11"
SRCREV_FORMAT .= "_pkcs11-sys"
SRCREV_pkcs11-sys = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/pkcs11/pkcs11-sys"
SRCREV_FORMAT .= "_test-common"
SRCREV_test-common = "${IIS_SRCREV}"
EXTRA_OECARGO_PATHS += "${WORKDIR}/test-common"
