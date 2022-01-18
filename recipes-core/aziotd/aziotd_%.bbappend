SRC_URI += "file://0001-Change-panic-strategy.patch"
SRC_URI += "file://0001-Add-aziot-keys.h-unused-in-current-recipe-version.patch"

do_compile_prepend () {
	echo "***********"
    echo "${WORKDIR}"
    sed -i '10s/^/# define SIZE_MAX __SIZE_MAX__\n/' ${WORKDIR}/git/tpm/aziot-tpm-sys/azure-iot-hsm-c/deps/c-shared/testtools/ctest/src/ctest.c
	#rm ${WORKDIR}/git/tpm/aziot-tpm-sys/azure-iot-hsm-c/deps/c-shared/testtools/ctest/src/ctest.c
}
