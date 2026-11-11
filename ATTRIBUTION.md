# Attribution

Resident Evil Native is a source export of the local nx2android checkout with its Resident Evil HD remaster work. That checkout had no Git commits, so an exact export commit cannot be supplied. The export manifest records copied file paths; it does not establish individual authorship.

- [nx2android](https://github.com/shirai91/nx2android): Android host integration, porter, GUI, shared profiles, build tools, and tests. Its README declares MIT licensing through nxnative/LICENSE. Preserve existing authorship and inline notices.
- [nxnative](https://github.com/seedds/nxnative): native execution runtime, graphics translation, extraction and rewriting tools. MIT, copyright (c) 2026 seedds; original license retained in [nxnative/LICENSE](nxnative/LICENSE) and the [root LICENSE](LICENSE).
- Selected shared improvements were integrated from [avanza-git/nx2android-revilhd](https://github.com/avanza-git/nx2android-revilhd/tree/5e4ea3b5953944163987ecc2752258e551c3ba06), revision `5e4ea3b5953944163987ecc2752258e551c3ba06`. See the [integration record](docs/UPSTREAM_INTEGRATION.md). Cache receipts and bounded shader checks retain their inline attribution to thehobbit85/nxnative at `1f01e28c87da` under MIT.
- Resident Evil movie timing observations reference masagrator and contributors' [FPSLocker-Warehouse](https://github.com/masagrator/FPSLocker-Warehouse); see the profile's patches.py and porter/fpslocker.py. The outside-save-room naming fix references eleval's BhdTool, as documented in patches.py.
- Vendored dependencies and adapted code keep their original terms: see the [third-party inventory](nxnative/dm/third_party/README.md), including Ryujinx, Vulkan headers, libvpx, stb_vorbis, bcdec, zstd, libadrenotools, the fusion pixel font, FLIP, deko3d, and MacNativeGames. Inline license notices are retained. libadrenotools' notices are in nxnative/dm/third_party/libadrenotools/LICENSE and lib/linkernsbypass/LICENSE.

Resident Evil and associated game content and marks belong to their respective owners. No ownership of game code, art, music, movies, or extracted shaders is asserted by this project.
