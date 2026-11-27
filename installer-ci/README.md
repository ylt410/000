# FiveStarPort installer verifier

The workflow builds the standalone macOS verifier from the MIT-licensed
FiveStarPort installer, archive reader and OpenIV expander. The workflow uses
GitHub's standard macOS runner. Its smoke tests create a synthetic package and
verify that an incorrect payload digest fails. The published artifact contains
the two executable utilities, documentation and a checksum.

On Apple Silicon macOS 13 or later, unpack the tool artifact and run:

```sh
./verify-install /path/to/Full.zip /path/to/FULL_RESULTS.json ./INSTALL_RESULTS.json
```

The Full receipt supplies the ZIP SHA-256, the package root, the destination
paths and their hashes, and the optional ASI name and hash. The verifier runs
the real unpack, install and OpenIV expansion paths in a temporary directory
and checks the expanded files against the receipt. It verifies Full packages
containing file additions. Runtime behavior still requires a device test.

Build the tools on a Mac with `bash installer-ci/build.sh out`. The only
source transformations isolate the verifier's Mods and cache paths from the
user's app folders. The Mac build needs the system SDK, Swift, zlib and
libarchive. Redistribution notices for the libarchive headers are in
`src/libarchive/LICENSE.txt`.
