- [x] Logs aren't being captured correctly. They are just the web requests, not the actual inputs and inference.
- [x] Change the boilerplate docstring for signatures
- [x] Change signature template class format "Categorizer" -> "CategorizerSignature"
- Boilerplate for modules also sucks. Especially `self.predictor` pattern
- [x] Edit all the template comments
- New command: `dspy-cli generate module [ModuleName] -s [signature]`
- New command: `dspy-cli generate signature [SignatureName]`
- New command: `dspy-cli generate scaffold [ProgramName]` 
- New command: `dspy-cli run -m predict "question -> answer"`
- UI: When starting a server, there's also a webpage
    - Root views all the programs
    - Click a program to use it
- [x] Remove /run from the program endpoints

To try:

- [x] Edit the signature
- [x] Edit the module
- [x] Change the default model to anthropic
- [x] Change the default model to LM Studio
- [x] Create a new program
- [x] Create a new module for an existing signature
- [x] Change a program to not use the default
