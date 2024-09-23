# Clone iotedge and checkout 1.5.11
cd ~/code/iotedge
git checkout 1.5.11

# generate iotedge bitbake
cd ~/code/iotedge/edgelet/iotedge
cargo-bitbake bitbake
cp iotedge_0.1.0.bb ~/code/yocto-workdir/meta-iotedge/poky/meta-iotedge/recipes-core/iotedge/iotedge_1.5.11.bb

# generate aziot-edge bitbake
cd ~/code/iotedge/edgelet/aziot-edge
cargo-bitbake bitbake
cp aziot-edged_0.1.0.bb ~/code/yocto-workdir/meta-iotedge/poky/meta-iotedge/recipes-core/aziot-edged/aziot-edged_1.5.11.bb

# clone iot-identity-service and checkout 1.5.3
cd ~/code/iot-identity-service
git checkout 1.5.3

# generate aziot-keys bitbake
cd ~/code/iot-identity-service/key/aziot-keys
cargo-bitbake bitbake
cp aziot-keys_0.1.0.bb ~/code/yocto-workdir/meta-iotedge/recipes-core/aziot-keys/aziot-keys_1.5.3.bb

# generate aziotctl bitbake
# first aziot-keyd dependency
cd ~/code/iot-identity-service/keys/aziot-keyd
cargo add --build bindgen@0.69.4 
cd ~/code/iot-identity-service/aziotctl
cargo-bitbake bitbake
cp aziotctl_1.5.3.bb ~/code/yocto-workdir/meta-iotedge/recipes-core/aziotctl/aziotctl_1.5.3.bb

# generate aziotd bitbake
cd ~/code/iot-identity-service/aziotd
cargo-bitbake bitbake
cp aziotd_1.5.3.bb ~/code/yocto-workdir/meta-iotedge/recipes-core/aziotd/aziotd_1.5.3.bb

# patch CARGO_SRC_DIR
sed -i "s/CARGO_SRC_DIR = \"iotedge\"/CARGO_SRC_DIR = \"edgelet\/iotedge\"/" ~/code/yocto-workdir/meta-iotedge/poky/meta-iotedge/recipes-core/iotedge/iotedge_1.5.11.bb

# patch CARGO_SRC_DIR
sed -i "s/CARGO_SRC_DIR = \"aziot-edged\"/CARGO_SRC_DIR = \"edgelet\/aziot-edged\"/" ~/code/yocto-workdir/meta-iotedge/poky/meta-iotedge/recipes-core/aziot-edged/aziot-edged_1.5.11.bb

# Patch iotedge
PATCH_TARGET="$HOME/code/yocto-workdir/meta-iotedge/poky/meta-iotedge/recipes-core/iotedge/iotedge_1.5.11.bb $HOME/code/yocto-workdir/meta-iotedge/poky/meta-iotedge/recipes-core/aziot-edged/aziot-edged_1.5.11.bb"
sed -i "s/destsuffix=aziot-cert-client-async/destsuffix=cert\/aziot-cert-client-async;subpath=cert\/aziot-cert-client-async/" $PATCH_TARGET
sed -i "s/destsuffix=aziot-cert-common-http/destsuffix=cert\/aziot-cert-common-http;subpath=cert\/aziot-cert-common-http/" $PATCH_TARGET
sed -i "s/destsuffix=aziot-certd-config/destsuffix=cert\/aziot-certd-config;subpath=cert\/aziot-certd-config/" $PATCH_TARGET
sed -i "s/destsuffix=aziot-identity-client-async/destsuffix=identity\/aziot-identity-client-async;subpath=identity\/aziot-identity-client-async/" $PATCH_TARGET
sed -i "s/destsuffix=aziot-identity-common-http/destsuffix=identity\/aziot-identity-common-http;subpath=identity\/aziot-identity-common-http/" $PATCH_TARGET
sed -i "s/destsuffix=aziot-identity-common/destsuffix=identity\/aziot-identity-common;subpath=identity\/aziot-identity-common/" $PATCH_TARGET
sed -i "s/destsuffix=aziot-identityd-config/destsuffix=identity\/aziot-identityd-config;subpath=identity\/aziot-identityd-config/" $PATCH_TARGET
sed -i "s/destsuffix=aziot-key-client-async/destsuffix=key\/aziot-key-client-async;subpath=key\/aziot-key-client-async/" $PATCH_TARGET
sed -i "s/destsuffix=aziot-key-client/destsuffix=key\/aziot-key-client;subpath=key\/aziot-key-client/" $PATCH_TARGET
sed -i "s/destsuffix=aziot-key-common-http/destsuffix=key\/aziot-key-common-http;subpath=key\/aziot-key-common-http/" $PATCH_TARGET
sed -i "s/destsuffix=aziot-key-common/destsuffix=key\/aziot-key-common;subpath=key\/aziot-key-common/" $PATCH_TARGET
sed -i "s/destsuffix=aziot-key-openssl-engine/destsuffix=key\/aziot-key-openssl-engine;subpath=key\/aziot-key-openssl-engine/" $PATCH_TARGET
sed -i "s/destsuffix=aziot-keyd-config/destsuffix=key\/aziot-keyd-config;subpath=key\/aziot-keyd-config/" $PATCH_TARGET
sed -i "s/destsuffix=aziot-keys-common/destsuffix=key\/aziot-keys-common;subpath=key\/aziot-keys-common/" $PATCH_TARGET
sed -i "s/destsuffix=aziot-tpmd-config/destsuffix=tpm\/aziot-tpmd-config;subpath=tpm\/aziot-tpmd-config/" $PATCH_TARGET
sed -i "s/destsuffix=aziotctl-common/destsuffix=aziotctl\/aziotctl-common;subpath=aziotctl\/aziotctl-common/" $PATCH_TARGET
sed -i "s/destsuffix=cert-renewal/destsuffix=cert\/cert-renewal;subpath=cert\/cert-renewal/" $PATCH_TARGET
sed -i "s/destsuffix=pkcs11-sys/destsuffix=pkcs11\/pkcs11-sys;subpath=pkcs11\/pkcs11-sys/" $PATCH_TARGET
sed -i "s/destsuffix=pkcs11 /destsuffix=pkcs11\/pkcs11;subpath=pkcs11\/pkcs11 /" $PATCH_TARGET
sed -i "s/destsuffix=test-common/destsuffix=test-common;subpath=test-common/" $PATCH_TARGET
sed -i "s/destsuffix=openssl2/destsuffix=openssl2;subpath=openssl2/" $PATCH_TARGET
sed -i "s/destsuffix=openssl-sys2/destsuffix=openssl-sys2;subpath=openssl-sys2/" $PATCH_TARGET
sed -i "s/destsuffix=openssl-build/destsuffix=openssl-build;subpath=openssl-build/" $PATCH_TARGET
sed -i "s/destsuffix=logger/destsuffix=logger;subpath=logger/" $PATCH_TARGET
sed -i "s/destsuffix=config-common/destsuffix=config-common;subpath=config-common/" $PATCH_TARGET
sed -i "s/destsuffix=http-common/destsuffix=http-common;subpath=http-common/" $PATCH_TARGET
sed -i "s/\${WORKDIR}\/aziot-cert-client-async/\${WORKDIR}\/cert\/aziot-cert-client-async/" $PATCH_TARGET
sed -i "s/\${WORKDIR}\/aziot-cert-common-http/\${WORKDIR}\/cert\/aziot-cert-common-http/" $PATCH_TARGET
sed -i "s/\${WORKDIR}\/aziot-certd-config/\${WORKDIR}\/cert\/aziot-certd-config/" $PATCH_TARGET
sed -i "s/\${WORKDIR}\/aziot-identity-client-async/\${WORKDIR}\/identity\/aziot-identity-client-async/" $PATCH_TARGET
sed -i "s/\${WORKDIR}\/aziot-identity-common/\${WORKDIR}\/identity\/aziot-identity-common/" $PATCH_TARGET
sed -i "s/\${WORKDIR}\/aziot-identity-common-http/\${WORKDIR}\/identity\/aziot-identity-common-http/" $PATCH_TARGET
sed -i "s/\${WORKDIR}\/aziot-identityd-config/\${WORKDIR}\/identity\/aziot-identityd-config/" $PATCH_TARGET
sed -i "s/\${WORKDIR}\/aziot-key-client/\${WORKDIR}\/key\/aziot-key-client/" $PATCH_TARGET
sed -i "s/\${WORKDIR}\/aziot-key-client-async/\${WORKDIR}\/key\/aziot-key-client-async/" $PATCH_TARGET
sed -i "s/\${WORKDIR}\/aziot-key-common/\${WORKDIR}\/key\/aziot-key-common/" $PATCH_TARGET
sed -i "s/\${WORKDIR}\/aziot-key-common-http/\${WORKDIR}\/key\/aziot-key-common-http/" $PATCH_TARGET
sed -i "s/\${WORKDIR}\/aziot-key-openssl-engine/\${WORKDIR}\/key\/aziot-key-openssl-engine/" $PATCH_TARGET
sed -i "s/\${WORKDIR}\/aziot-keyd-config/\${WORKDIR}\/key\/aziot-keyd-config/" $PATCH_TARGET
sed -i "s/\${WORKDIR}\/aziot-keys-common/\${WORKDIR}\/key\/aziot-keys-common/" $PATCH_TARGET
sed -i "s/\${WORKDIR}\/aziot-tpmd-config/\${WORKDIR}\/tpm\/aziot-tpmd-config/" $PATCH_TARGET
sed -i "s/\${WORKDIR}\/aziotctl-common/\${WORKDIR}\/aziotctl\/aziotctl-common/" $PATCH_TARGET
sed -i "s/\${WORKDIR}\/cert-renewal/\${WORKDIR}\/cert\/cert-renewal/" $PATCH_TARGET
sed -i "s/\${WORKDIR}\/pkcs11/\${WORKDIR}\/pkcs11\/pkcs11/" $PATCH_TARGET
sed -i "s/\${WORKDIR}\/pkcs11-sys/\${WORKDIR}\/pkcs11\/pkcs11-sys/" $PATCH_TARGET
sed -i "s/file:\/\/MIT;md5=generateme /file:\/\/LICENSE;md5=0f7e3b1308cb5c00b372a6e78835732d file:\/\/THIRDPARTYNOTICES;md5=11604c6170b98c376be25d0ca6989d9b/"  $PATCH_TARGET

# Patch the branch hashes from iot-identity-service. Replace the
sed -i "s/\"main\"/\"72cea820a241aac81cf42bb6693a6e26ac25187c\"/"  $PATCH_TARGET

# Patch the licenses
SERVICE_PATCH_TARGET="$HOME/code/yocto-workdir/meta-iotedge/recipes-core/aziot-keys/aziot-keys_1.5.3.bb $HOME/code/yocto-workdir/meta-iotedge/recipes-core/aziotctl/aziotctl_1.5.3.bb $HOME/code/yocto-workdir/meta-iotedge/recipes-core/aziotd/aziotd_1.5.3.bb"
sed -i "s/file:\/\/MIT;md5=generateme/file:\/\/LICENSE;md5=4f9c2c296f77b3096b6c11a16fa7c66e/" $SERVICE_PATCH_TARGET

# Add pkgconfig to aziot-keys
sed -i "s/inherit cargo/inherit cargo pkgconfig/" $HOME/code/yocto-workdir/meta-iotedge/recipes-core/aziot-keys/aziot-keys_1.5.3.bb $HOME/code/yocto-workdir/meta-iotedge/recipes-core/aziotd/aziotd_1.5.3.bb

#Get the missing SRC_URI checksums 
bitbake aziot-keys
#copying the missing checksums into the bb file from the output error message.

# Generate aziot-keys patch
devtool modify aziot-keys
cd workspace/sources/aziot-keys
sed -i "/panic = \"abort\"/d" Cargo.toml
git commit -am "Remove panic"
devtool update-recipe aziot-keys

# repeat the previous SRC_URI and patch step for aziotctl and aziotd

# Also fix the rustdoc problem for aziotd
cd workspace/source/aziotd
sed -i "s/\/\/\/ The TPM's Endorsement Key/\/\/ The TPM's Endorsement Key/" tpm/aziot-tpmd/src/http/get_tpm_keys.rs tpm/aziot-tpm-common-http/src/lib.rs
sed -i "s/\/\/\/ The TPM's Storage Root Key/\/\/ The TPM's Storage Root Key/" tpm/aziot-tpmd/src/http/get_tpm_keys.rs tpm/aziot-tpm-common-http/src/lib.rs
git commit -am "Fix rustdoc warning"

# Patch aziot-keyd
cd keys/aziot-keyd
cargo add --build bindgen@0.69.4

# Add the following to build.rs in aziot-keyd
    // to bindgen, and lets you build up options for
    // the resulting bindings.
    let bindings = bindgen::Builder::default()
        // The input header we would like to generate
        // bindings for.
        .header("../aziot-keys/aziot-keys.h")
        // Tell cargo to invalidate the built crate whenever any of the
        // included header files changed.
        .parse_callbacks(Box::new(bindgen::CargoCallbacks::new()))
        // Finish the builder and generate the bindings.
        .generate()
        // Unwrap the Result and panic on failure.
        .expect("Unable to generate bindings");

    bindings
        .write_to_file("src/keys.generated.rs")
        .expect("Couldn't write bindings!");
git commit -a -m "Fix keys.generated.rs bindings"
devtool update-recipe aziotd

# Make sure aziotd builds
bitbake aziotd

# Run Fix up the aziot-edged and iotedge SRC_URI hashes by running this command and copying the output.
bitbake aziot-edged

# patch iotedge
devtool modify iotedge
cd workspace/sources/iotedge
sed -i "/panic = 'abort'/d" edgelet/Cargo.toml
sed -i '/source = "git/d' edgelet/Cargo.lock
cd iotedge
ln -s ../Cargo.lock Cargo.lock
git add -A
git commit -m "Fix Cargo.lock and panic"
devtool update-recipe iotedge

devtool modify aziot-edged
cd workspace/sources/aziot-edged
sed -i "/panic = 'abort'/d" edgelet/Cargo.toml
sed -i '/source = "git/d' edgelet/Cargo.lock
cd aziot-edged
ln -s ../Cargo.lock Cargo.lock
git add -A
git commit -m "Fix Cargo.lock and panic"
devtool update-recipe aziot-edged