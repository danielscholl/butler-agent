# Changelog

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
