- [x] Logs aren't being captured correctly. They are just the web requests, not the actual inputs and inference.
- [x] Change the boilerplate docstring for signatures
- [x] Change signature template class format "Categorizer" -> "CategorizerSignature"
- [x] Boilerplate for modules also sucks. Especially `self.predictor` pattern
- [x] Edit all the template comments
- New command: `dspy-cli generate module [ModuleName] -s [signature]`
- New command: `dspy-cli generate signature [SignatureName]`
- [x] New command: `dspy-cli generate scaffold [ProgramName]` 
- New command: `dspy-cli demo -m predict "question -> answer"`
- Add the `destroy` command.
- UI: When starting a server, there's also a webpage
    - Root views all the programs
    - Click a program to use it
- [x] Remove /run from the program endpoints
- Load local API keys if they exist and aren't in the env
- Handle camel case, snake case, etc and normalize all based on how they're entered in the CLI.
- [x] Change default project folder name
- [x] Change help banner
- [ ] If there are two programs/modules with the same name abort and throw an error
- [ ] UI: When I have multiple modules referencing one signature, the signature data isn't loaded.
- [ ] UI: Have custom typed fields and validation

Examples to Build as Dogfood:

- Researcher
- POI conflater
- Summarizer
- Image alt-text description

To try:

- [x] Edit the signature
- [x] Edit the module
- [x] Change the default model to anthropic
- [x] Change the default model to LM Studio
- [x] Create a new program
- [x] Create a new module for an existing signature
- [x] Change a program to not use the default
- Test all the different modules with scaffold and running them
- Stress test an endpoint
