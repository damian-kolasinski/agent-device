import fs from 'node:fs';
import { pathToFileURL } from 'node:url';
const [packagePath, stateDir, session, udid] = process.argv.slice(2);
process.env.AGENT_DEVICE_STATE_DIR = stateDir;
const { createAgentDeviceClient } = await import(pathToFileURL(`${packagePath}/dist/src/index.js`));
const client = createAgentDeviceClient({session, cwd:process.cwd(), stateDir, platform:'ios', udid});
try {
  console.log(JSON.stringify({success:true,data:await client.batch.run({steps:JSON.parse(fs.readFileSync(0,'utf8'))})}));
} catch (error) {
  console.log(JSON.stringify({success:false,error:{code:error.code,message:error.message,details:error.details}}));
  process.exitCode=1;
}
