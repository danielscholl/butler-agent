# Changelog

## [0.2.2](https://github.com/danielscholl/butler-agent/compare/butler-agent-v0.2.1...butler-agent-v0.2.2) (2025-11-13)


### Bug Fixes

* Remove pull_request_target to prevent secret exfiltration ([#39](https://github.com/danielscholl/butler-agent/issues/39)) ([e84f272](https://github.com/danielscholl/butler-agent/commit/e84f27233bf18508ef9170916605578d260d9b0f))

## [0.2.1](https://github.com/danielscholl/butler-agent/compare/butler-agent-v0.2.0...butler-agent-v0.2.1) (2025-11-06)


### Code Refactoring

* **cluster:** consolidate lifecycle operations to create/remove model ([#34](https://github.com/danielscholl/butler-agent/issues/34)) ([e1ee284](https://github.com/danielscholl/butler-agent/commit/e1ee28405bf0803ae9c244e90ffc6f9bfa87e86c))

## [0.2.0](https://github.com/danielscholl/butler-agent/compare/butler-agent-v0.1.10...butler-agent-v0.2.0) (2025-11-06)


### ⚠ BREAKING CHANGES

* **config:** Removed support for .local/infra/ shared templates and custom template. Only minimal and default templates remain. Users must migrate configs to cluster-specific locations.

### Code Refactoring

* **config:** simplify cluster configuration discovery ([#32](https://github.com/danielscholl/butler-agent/issues/32)) ([f6e9f2c](https://github.com/danielscholl/butler-agent/commit/f6e9f2c42b1d520204dc18801336f34bf46a4ec1))

## [0.1.10](https://github.com/danielscholl/butler-agent/compare/butler-agent-v0.1.9...butler-agent-v0.1.10) (2025-11-06)


### Bug Fixes

* **cluster:** adjust cluster creation success handling based on addon… ([#29](https://github.com/danielscholl/butler-agent/issues/29)) ([7381fda](https://github.com/danielscholl/butler-agent/commit/7381fdae9eda28a9f342879d25d852f754fdbaf9))

## [0.1.9](https://github.com/danielscholl/butler-agent/compare/butler-agent-v0.1.8...butler-agent-v0.1.9) (2025-11-06)


### Features

* migrate to .local storage with enhanced cluster config management ([#27](https://github.com/danielscholl/butler-agent/issues/27)) ([859c782](https://github.com/danielscholl/butler-agent/commit/859c7821498a3813aeb18bb978aa88458232592c))

## [0.1.8](https://github.com/danielscholl/butler-agent/compare/butler-agent-v0.1.7...butler-agent-v0.1.8) (2025-11-05)


### Bug Fixes

* **core:** fix issues in 2 files ([#25](https://github.com/danielscholl/butler-agent/issues/25)) ([3dd748f](https://github.com/danielscholl/butler-agent/commit/3dd748ffda0f19c261acd4ebfb0e5dde00e4eb56))

## [0.1.7](https://github.com/danielscholl/butler-agent/compare/butler-agent-v0.1.6...butler-agent-v0.1.7) (2025-11-05)


### Bug Fixes

* address code review feedback for status branch ([#23](https://github.com/danielscholl/butler-agent/issues/23)) ([619d2de](https://github.com/danielscholl/butler-agent/commit/619d2ded75a2aad7a80a4c754e867f8b72b6701d))

## [0.1.6](https://github.com/danielscholl/butler-agent/compare/butler-agent-v0.1.5...butler-agent-v0.1.6) (2025-11-05)


### Features

* implement two-phase addon architecture with config merge ([#21](https://github.com/danielscholl/butler-agent/issues/21)) ([0a0f1f1](https://github.com/danielscholl/butler-agent/commit/0a0f1f17782ec6b1454ade1b2c3549c447b7a9da))

## [0.1.5](https://github.com/danielscholl/butler-agent/compare/butler-agent-v0.1.4...butler-agent-v0.1.5) (2025-11-03)


### Features

* **cli:** implement extensible keybinding system with shell command execution ([#19](https://github.com/danielscholl/butler-agent/issues/19)) ([8fb907a](https://github.com/danielscholl/butler-agent/commit/8fb907aa30ce760b8264359a0403f1ab5c903fe2))

## [0.1.4](https://github.com/danielscholl/butler-agent/compare/butler-agent-v0.1.3...butler-agent-v0.1.4) (2025-11-03)


### Features

* **cluster:** export and persist kubeconfig on cluster creation ([#18](https://github.com/danielscholl/butler-agent/issues/18)) ([228b198](https://github.com/danielscholl/butler-agent/commit/228b198fb7c46c428b6d045a84020b2fae549d08))
* **kubectl:** add Kubernetes resource management capabilities ([#16](https://github.com/danielscholl/butler-agent/issues/16)) ([0d52770](https://github.com/danielscholl/butler-agent/commit/0d527706e1cb1324ef51246d2dfb0b5715261f56))

## [0.1.3](https://github.com/danielscholl/butler-agent/compare/butler-agent-v0.1.2...butler-agent-v0.1.3) (2025-11-02)


### Features

* Add cluster lifecycle management and custom KinD configurations ([#12](https://github.com/danielscholl/butler-agent/issues/12)) ([8c917cb](https://github.com/danielscholl/butler-agent/commit/8c917cbc86baf5033432d2d81852565949ba5a83))

## [0.1.2](https://github.com/danielscholl/butler-agent/compare/butler-agent-v0.1.1...butler-agent-v0.1.2) (2025-11-02)


### Bug Fixes

* foundation security and correctness fixes ([#10](https://github.com/danielscholl/butler-agent/issues/10)) ([ecbf6ea](https://github.com/danielscholl/butler-agent/commit/ecbf6ea6fe8cd7d73755ee8c15e80fd225273c40))

## [0.1.1](https://github.com/danielscholl/butler-agent/compare/butler-agent-v0.1.0...butler-agent-v0.1.1) (2025-11-02)


### Features

* **agent:** implement memory, persistence, and enhanced middleware ([ac5252a](https://github.com/danielscholl/butler-agent/commit/ac5252a6df87c5e0aa9c53b0aa91a67afe9c6e0e))
* **azure:** add dynamic client selection for codex models ([ad2b0f9](https://github.com/danielscholl/butler-agent/commit/ad2b0f99fc3ffce98b3586e29e6b37aef732f75d))
* **cli:** integrate cross-platform clear_screen and enhance reset flow ([fe9692a](https://github.com/danielscholl/butler-agent/commit/fe9692a48803dce6c407bfc28814ec0a151f9b2f))
* **display:** implement minimal UI with health checks and status bar ([d3b0743](https://github.com/danielscholl/butler-agent/commit/d3b07434a2d1cf86e49a1a919e13d401e38998e1))
* **llm:** add OpenAI Responses API support for gpt-5-codex model ([31fb7bf](https://github.com/danielscholl/butler-agent/commit/31fb7bf8c80633a4a2cc29010f6cf0f5d577be33))
* replace /new command with /clear ([929861c](https://github.com/danielscholl/butler-agent/commit/929861c76900538b5d74448742acb808c72a56b5))


### Bug Fixes

* **ci:** correct codecov upload configuration parameter ([e2ed636](https://github.com/danielscholl/butler-agent/commit/e2ed6369a3f3c18882706d443fe39b82e8c2d032))
* **clients:** correct Azure OpenAI client parameter name ([515fd30](https://github.com/danielscholl/butler-agent/commit/515fd30bc22d8f30fdc6f938b4add98057b09f18))
* **cli:** remove deprecated --short flag from kubectl version check ([6d4402e](https://github.com/danielscholl/butler-agent/commit/6d4402eae07e3a28e3d02863a24f78929fdc11b9))


### Documentation

* add comprehensive architecture refactor plan ([b0babc3](https://github.com/danielscholl/butler-agent/commit/b0babc3e7ff3d78a1665862bbef09b460fc6e902))
* add comprehensive contributing guide and update README ([3ea0ab4](https://github.com/danielscholl/butler-agent/commit/3ea0ab49ab9835a7dd55117deb1b5619140e5f95))
* **readme:** restructure documentation with streamlined quick start ([769f684](https://github.com/danielscholl/butler-agent/commit/769f6841a74cef1c09362430b7f80506a8411ddb))
* remove legacy architecture & implementation analysis documents ([3543353](https://github.com/danielscholl/butler-agent/commit/35433532bcee36c506cc58989aac68973e8575fc))


### Code Refactoring

* **cli:** improve query output formatting by removing redundant prompt display ([19f9e55](https://github.com/danielscholl/butler-agent/commit/19f9e554133f746191b5bd580fa25a84e339fb88))
* **cli:** move clear_screen import to module level and add error handling ([f50c967](https://github.com/danielscholl/butler-agent/commit/f50c967157c07601087803fb8b8bf565621dc4c8))
* **cli:** simplify health check command to remove tool-specific options ([c7fa63f](https://github.com/danielscholl/butler-agent/commit/c7fa63fdb93aa0fafec95e1e6390a9d4f563b0da))
* **llm:** simplify OpenAI client initialization with direct kwargs ([82476ae](https://github.com/danielscholl/butler-agent/commit/82476ae705f2ac5897cfbd31e5430311001e0042))
* modernize architecture with framework best practices ([68a163b](https://github.com/danielscholl/butler-agent/commit/68a163b6de66c7b460124603042e8fceb3a88af5))
* remove Anthropic and Gemini providers, focus on OpenAI/Azure ([26a9133](https://github.com/danielscholl/butler-agent/commit/26a91332a3e318c2318e9e1e40730b411ff55071))
* remove unused global variable and add error comment ([9a3a295](https://github.com/danielscholl/butler-agent/commit/9a3a29518d78e60e75c45819e4d99263cddcd159))
* rename butler package to agent and externalize system prompt ([13ce77f](https://github.com/danielscholl/butler-agent/commit/13ce77f93a08b1e6367819cf720fd84f1bd46637))
* rename butler to agent across codebase ([93d1ae2](https://github.com/danielscholl/butler-agent/commit/93d1ae228f4697c0d5a79378931c7d065b3563ba))
* **types:** modernize type hints and fix middleware compatibility ([7b7c26a](https://github.com/danielscholl/butler-agent/commit/7b7c26a8795ca45f710c005e53678737e8911f26))


### Tests

* **tests:** update unit tests to rely on env vars for provider setup ([aa1fb8c](https://github.com/danielscholl/butler-agent/commit/aa1fb8c226271c98ea3db1420f4a01ead4e8eeed))


### Continuous Integration

* **release:** use dedicated token for release-please workflow ([#8](https://github.com/danielscholl/butler-agent/issues/8)) ([bb2a635](https://github.com/danielscholl/butler-agent/commit/bb2a63512f7e89adb82a9e76921ea4ba779ce0ea))
