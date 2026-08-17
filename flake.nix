{
  description = "PlanetSide 2 archive scraper";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { nixpkgs, ... }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];

      forAllSystems = nixpkgs.lib.genAttrs systems;
    in {
      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs {
            inherit system;
          };

          python = pkgs.python3.withPackages (ps: [
            ps.playwright
          ]);
        in {
          default = pkgs.mkShell {
            packages = [
              python
              pkgs.chromium
            ];

            env = {
              PLAYWRIGHT_CHROMIUM =
                "${pkgs.chromium}/bin/chromium";
            };
          };
        });
    };
}
