## Never to do

- Never deploy a lambda with architecture X86_64 from Linux, this cause issues in the lambda and vicerversa
- When deploy lambda runtime java must not specific properties  Role either FunctionName
- To deploy a lambda java is must
  - Delete if exist folder .aws-sam
  - sam build --template template_wb.yaml
  - sam deploy -t .aws-sam/build/template_wb.yaml
- Error:
  - Status Reason is An error occurred during function initialization."
    - Comment these in the first deply lambda java
    ```yaml
    # Remove AutoPublishAlias: live
    ```
