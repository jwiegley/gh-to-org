{
  description = "Sync GitHub issues to Org-mode files with bidirectional awareness";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        # Override Python packages to fix build issues
        pythonOverrides = final: prev: {
          # typer has failing tests in nixpkgs, skip them
          typer = prev.typer.overridePythonAttrs (old: {
            doCheck = false;
          });
        };

        python = pkgs.python311.override {
          packageOverrides = pythonOverrides;
        };

        # Build the Python application
        gh-org-sync = python.pkgs.buildPythonApplication {
          pname = "gh-org-sync";
          version = "1.0.0";
          pyproject = true;

          src = ./.;

          # Build system dependency
          build-system = [
            python.pkgs.hatchling
          ];

          # Runtime dependencies from pyproject.toml
          dependencies = with python.pkgs; [
            pydantic
            typer
            rich
            httpx
          ];

          # Wrap the executable so it can find gh CLI at runtime
          nativeBuildInputs = [ pkgs.makeWrapper ];

          postInstall = ''
            wrapProgram $out/bin/gh-org-sync \
              --prefix PATH : ${pkgs.lib.makeBinPath [ pkgs.gh ]}
          '';

          # Don't check tests during build (can be run separately in dev shell)
          doCheck = false;

          meta = with pkgs.lib; {
            description = "Sync GitHub issues to Org-mode files with bidirectional awareness";
            homepage = "https://github.com/johnw/github-issues-to-org";
            license = licenses.mit;
            maintainers = [ ];
            mainProgram = "gh-org-sync";
          };
        };

      in
      {
        # Default package for `nix build`
        packages.default = gh-org-sync;
        packages.gh-org-sync = gh-org-sync;

        # Dev shell for `nix develop`
        devShells.default = pkgs.mkShell {
          buildInputs = [
            # Python with all dependencies
            python

            # Runtime dependencies
            python.pkgs.pydantic
            python.pkgs.typer
            python.pkgs.rich
            python.pkgs.httpx

            # Dev dependencies
            python.pkgs.pytest
            python.pkgs.pytest-asyncio
            python.pkgs.mypy
            python.pkgs.ruff

            # Build system
            python.pkgs.hatchling
            python.pkgs.pip

            # GitHub CLI
            pkgs.gh
          ];

          shellHook = ''
            echo "gh-org-sync development environment"
            echo "Python: $(python --version)"
            echo "GitHub CLI: $(gh --version | head -n1)"
            echo ""
            echo "Available commands:"
            echo "  pytest          - Run tests"
            echo "  mypy src        - Type check"
            echo "  ruff check      - Lint code"
            echo "  ruff format     - Format code"
            echo ""
            echo "Install in editable mode:"
            echo "  pip install -e ."
            echo ""

            # Add current directory to PYTHONPATH for development
            export PYTHONPATH="${toString ./.}/src:$PYTHONPATH"
          '';
        };

        # App definition for easy running with `nix run`
        apps.default = {
          type = "app";
          program = "${gh-org-sync}/bin/gh-org-sync";
        };
      }
    );
}
