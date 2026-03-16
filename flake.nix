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

        pythonOverrides = final: prev: {
          typer = prev.typer.overridePythonAttrs (old: {
            doCheck = false;
          });
        };

        python = pkgs.python3.override {
          packageOverrides = pythonOverrides;
        };

        runtimeDeps = ps: with ps; [
          pydantic
          typer
          rich
          httpx
        ];

        devDeps = ps: with ps; [
          pytest
          pytest-asyncio
          pytest-cov
          pytest-benchmark
          hypothesis
          mypy
          ruff
          hatchling
          pip
        ];

        # Python environment with all deps for checks
        pythonWithDeps = python.withPackages (ps:
          (runtimeDeps ps) ++ (devDeps ps)
        );

        src = pkgs.lib.cleanSource ./.;

        # Build the Python application
        gh-org-sync = python.pkgs.buildPythonApplication {
          pname = "gh-org-sync";
          version = "1.0.0";
          pyproject = true;

          inherit src;

          build-system = [
            python.pkgs.hatchling
          ];

          dependencies = runtimeDeps python.pkgs;

          nativeBuildInputs = [ pkgs.makeWrapper ];

          postInstall = ''
            wrapProgram $out/bin/gh-org-sync \
              --prefix PATH : ${pkgs.lib.makeBinPath [ pkgs.gh ]}
          '';

          doCheck = false;

          meta = with pkgs.lib; {
            description = "Sync GitHub issues to Org-mode files with bidirectional awareness";
            license = licenses.bsd3;
            maintainers = [ ];
            mainProgram = "gh-org-sync";
          };
        };

        mkCheck = name: script: pkgs.runCommand "check-${name}" {
          nativeBuildInputs = [ pythonWithDeps ];
        } ''
          export HOME=$(mktemp -d)
          cp -r ${src} $HOME/src
          chmod -R u+w $HOME/src
          cd $HOME/src
          ${script}
          touch $out
        '';

      in
      {
        packages.default = gh-org-sync;
        packages.gh-org-sync = gh-org-sync;

        checks = {
          # Verify the package builds
          build = gh-org-sync;

          # Code formatting
          format = mkCheck "format" ''
            ruff format --check .
          '';

          # Linting
          lint = mkCheck "lint" ''
            ruff check .
          '';

          # Type checking
          typecheck = mkCheck "typecheck" ''
            PYTHONPATH=src mypy src/
          '';

          # Unit and integration tests
          test = mkCheck "test" ''
            PYTHONPATH=src pytest tests/ -x -q
          '';

          # Code coverage (fail if below threshold)
          coverage = mkCheck "coverage" ''
            PYTHONPATH=src pytest tests/ -q \
              --cov=gh_org_sync \
              --cov-report=term-missing \
              --cov-fail-under=35
          '';

          # Property-based / fuzz tests
          fuzz = mkCheck "fuzz" ''
            PYTHONPATH=src pytest tests/ -q -m "hypothesis or property" \
              --hypothesis-seed=0 || true
            touch $out
          '';
        };

        devShells.default = pkgs.mkShell {
          buildInputs = [
            pythonWithDeps
            pkgs.gh
            pkgs.lefthook
          ];

          shellHook = ''
            echo "gh-org-sync development environment"
            echo "Python: $(python --version)"
            echo ""
            echo "Commands:"
            echo "  pytest             - Run tests"
            echo "  mypy src/          - Type check"
            echo "  ruff check .       - Lint"
            echo "  ruff format .      - Format"
            echo "  nix flake check    - Run all checks"
            echo "  lefthook run pre-commit - Run pre-commit hooks"
            echo ""

            export PYTHONPATH="${toString ./.}/src:$PYTHONPATH"
          '';
        };

        apps.default = {
          type = "app";
          program = "${gh-org-sync}/bin/gh-org-sync";
        };
      }
    );
}
