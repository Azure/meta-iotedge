# Source configuration with individual subpaths for iot-identity-service components
SRC_URI += " \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=aziot-cert-client-async;destsuffix=cert/aziot-cert-client-async;subpath=cert/aziot-cert-client-async \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=aziot-cert-common-http;destsuffix=cert/aziot-cert-common-http;subpath=cert/aziot-cert-common-http \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=aziot-certd-config;destsuffix=cert/aziot-certd-config;subpath=cert/aziot-certd-config \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=aziot-identity-client-async;destsuffix=identity/aziot-identity-client-async;subpath=identity/aziot-identity-client-async \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=aziot-identity-common-http;destsuffix=identity/aziot-identity-common-http;subpath=identity/aziot-identity-common-http \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=aziot-identity-common;destsuffix=identity/aziot-identity-common;subpath=identity/aziot-identity-common \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=aziot-identityd-config;destsuffix=identity/aziot-identityd-config;subpath=identity/aziot-identityd-config \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=aziot-key-client-async;destsuffix=key/aziot-key-client-async;subpath=key/aziot-key-client-async \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=aziot-key-client;destsuffix=key/aziot-key-client;subpath=key/aziot-key-client \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=aziot-key-common-http;destsuffix=key/aziot-key-common-http;subpath=key/aziot-key-common-http \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=aziot-key-common;destsuffix=key/aziot-key-common;subpath=key/aziot-key-common \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=aziot-key-openssl-engine;destsuffix=key/aziot-key-openssl-engine;subpath=key/aziot-key-openssl-engine \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=aziot-keyd-config;destsuffix=key/aziot-keyd-config;subpath=key/aziot-keyd-config \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=aziot-keys-common;destsuffix=key/aziot-keys-common;subpath=key/aziot-keys-common \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=aziot-tpmd-config;destsuffix=tpm/aziot-tpmd-config;subpath=tpm/aziot-tpmd-config \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=aziotctl-common;destsuffix=aziotctl/aziotctl-common;subpath=aziotctl/aziotctl-common \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=cert-renewal;destsuffix=cert/cert-renewal;subpath=cert/cert-renewal \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=config-common;destsuffix=config-common;subpath=config-common \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=http-common;destsuffix=http-common;subpath=http-common \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=logger;destsuffix=logger;subpath=logger \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=openssl-build;destsuffix=openssl-build;subpath=openssl-build \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=openssl-sys2;destsuffix=openssl-sys2;subpath=openssl-sys2 \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=openssl2;destsuffix=openssl2;subpath=openssl2 \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=pkcs11-sys;destsuffix=pkcs11/pkcs11-sys;subpath=pkcs11/pkcs11-sys \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=pkcs11;destsuffix=pkcs11/pkcs11;subpath=pkcs11/pkcs11 \
           git://github.com/Azure/iot-identity-service.git;protocol=https;nobranch=1;name=test-common;destsuffix=test-common;subpath=test-common \
"

# Source revisions
SRCREV_aziot-cert-client-async = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_aziot-cert-common-http = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_aziot-certd-config = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_aziot-identity-client-async = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_aziot-identity-common-http = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_aziot-identity-common = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_aziot-identityd-config = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_aziot-key-client-async = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_aziot-key-client = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_aziot-key-common-http = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_aziot-key-common = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_aziot-key-openssl-engine = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_aziot-keyd-config = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_aziot-keys-common = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_aziot-tpmd-config = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_aziotctl-common = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_cert-renewal = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_config-common = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_http-common = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_logger = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_openssl-build = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_openssl-sys2 = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_openssl2 = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_pkcs11-sys = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_pkcs11 = "${IOT_IDENTITY_SERVICE_SRCREV}"
SRCREV_test-common = "${IOT_IDENTITY_SERVICE_SRCREV}"

# Extra cargo paths for all the iot-identity-service components
EXTRA_OECARGO_PATHS += "${WORKDIR}/cert/aziot-cert-client-async"
EXTRA_OECARGO_PATHS += "${WORKDIR}/cert/aziot-cert-common-http"
EXTRA_OECARGO_PATHS += "${WORKDIR}/cert/aziot-certd-config"
EXTRA_OECARGO_PATHS += "${WORKDIR}/identity/aziot-identity-client-async"
EXTRA_OECARGO_PATHS += "${WORKDIR}/identity/aziot-identity-common-http"
EXTRA_OECARGO_PATHS += "${WORKDIR}/identity/aziot-identity-common"
EXTRA_OECARGO_PATHS += "${WORKDIR}/identity/aziot-identityd-config"
EXTRA_OECARGO_PATHS += "${WORKDIR}/key/aziot-key-client-async"
EXTRA_OECARGO_PATHS += "${WORKDIR}/key/aziot-key-client"
EXTRA_OECARGO_PATHS += "${WORKDIR}/key/aziot-key-common-http"
EXTRA_OECARGO_PATHS += "${WORKDIR}/key/aziot-key-common"
EXTRA_OECARGO_PATHS += "${WORKDIR}/key/aziot-key-openssl-engine"
EXTRA_OECARGO_PATHS += "${WORKDIR}/key/aziot-keyd-config"
EXTRA_OECARGO_PATHS += "${WORKDIR}/key/aziot-keys-common"
EXTRA_OECARGO_PATHS += "${WORKDIR}/tpm/aziot-tpmd-config"
EXTRA_OECARGO_PATHS += "${WORKDIR}/aziotctl/aziotctl-common"
EXTRA_OECARGO_PATHS += "${WORKDIR}/cert/cert-renewal"
EXTRA_OECARGO_PATHS += "${WORKDIR}/config-common"
EXTRA_OECARGO_PATHS += "${WORKDIR}/http-common"
EXTRA_OECARGO_PATHS += "${WORKDIR}/logger"
EXTRA_OECARGO_PATHS += "${WORKDIR}/openssl-build"
EXTRA_OECARGO_PATHS += "${WORKDIR}/openssl-sys2"
EXTRA_OECARGO_PATHS += "${WORKDIR}/openssl2"
EXTRA_OECARGO_PATHS += "${WORKDIR}/pkcs11/pkcs11-sys"
EXTRA_OECARGO_PATHS += "${WORKDIR}/pkcs11/pkcs11"
EXTRA_OECARGO_PATHS += "${WORKDIR}/test-common"
