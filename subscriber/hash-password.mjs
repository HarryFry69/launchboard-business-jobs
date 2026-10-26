import { randomBytes, scryptSync } from 'node:crypto';

async function hiddenPassword() {
  if (!process.stdin.isTTY) {
    let result = '';
    for await (const chunk of process.stdin) result += chunk.toString('utf8');
    return result.replace(/[\r\n]+$/, '');
  }
  process.stderr.write('Choose a strong password (at least 12 characters): ');
  process.stdin.setRawMode(true);
  process.stdin.resume();
  let password = '';
  return new Promise((resolve, reject) => {
    process.stdin.on('data', data => {
      for (const c of data.toString('utf8')) {
        if (c === '\u0003') { process.stdin.setRawMode(false); reject(new Error('Cancelled')); return; }
        if (c === '\r' || c === '\n') {
          process.stdin.setRawMode(false); process.stdin.pause();
          process.stderr.write('\n');
          resolve(password); return;
        }
        if (c === '\u007f') { password = password.slice(0, -1); continue; }
        password += c;
      }
    });
  });
}
try {
  const password = await hiddenPassword();
  if (password.length < 12 || password.length > 200) throw new Error('Password must be 12–200 characters');
  const salt = randomBytes(20);
  const digest = scryptSync(password, salt, 64);
  console.log('ACCESS_PASSWORD_HASH=scrypt:' + salt.toString('hex') + ':' + digest.toString('hex'));
  console.log('SESSION_SECRET=' + randomBytes(40).toString('hex'));
} catch (err) {
  console.error(err.message);
  process.exitCode = 1;
}
