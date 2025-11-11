import { execSync } from 'child_process';
import * as path from 'path';

const PROTO_DIR = path.resolve(__dirname, '../proto');
const OUT_DIR = path.resolve(__dirname, '../src/proto');

try {
  execSync(`protoc --plugin=protoc-gen-ts_proto=./node_modules/.bin/protoc-gen-ts_proto \
    --ts_proto_out=${OUT_DIR} \
    --ts_proto_opt=esModuleInterop=true \
    --proto_path=${PROTO_DIR} \
    ${PROTO_DIR}/*.proto`);
  
  console.log('Protocol buffers generated successfully');
} catch (error) {
  console.error('Error generating protocol buffers:', error);
  process.exit(1);
}
