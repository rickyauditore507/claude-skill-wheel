'use strict';

const vscode = require('vscode');
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const APP_DIR = path.join(os.homedir(), '.claude', 'skill-wheel');
const CONFIG_PATH = path.join(APP_DIR, 'config.json');

let child = null;
let output = null;
let statusItem = null;

function log(line) {
  if (output) output.appendLine(`[${new Date().toLocaleTimeString()}] ${line}`);
}

function projectDir() {
  const configured = vscode.workspace.getConfiguration('skillWheel').get('projectDir', '');
  return configured && configured.trim() ? configured.trim() : path.join(os.homedir(), 'skill-wheel');
}

function pythonPath(dir) {
  const configured = vscode.workspace.getConfiguration('skillWheel').get('pythonPath', '');
  if (configured && configured.trim()) return configured.trim();
  const venv = path.join(dir, '.venv', 'Scripts');
  const pythonw = path.join(venv, 'pythonw.exe');
  if (fs.existsSync(pythonw)) return pythonw;
  const python = path.join(venv, 'python.exe');
  if (fs.existsSync(python)) return python;
  return 'python';
}

function workspacePath() {
  const folders = vscode.workspace.workspaceFolders;
  return folders && folders.length ? folders[0].uri.fsPath : '';
}

function updateStatus(running) {
  if (!statusItem) return;
  const enabled = vscode.workspace.getConfiguration('skillWheel').get('showStatusBar', true);
  statusItem.text = running ? '$(circle-filled) Skill Wheel' : '$(circle-outline) Skill Wheel';
  statusItem.tooltip = running
    ? 'Skill Wheel 运行中 — 按住 Alt+` 选择 skill（点击停止）'
    : 'Skill Wheel 已停止（点击启动）';
  statusItem.color = running ? undefined : new vscode.ThemeColor('disabledForeground');
  if (enabled) statusItem.show();
  else statusItem.hide();
}

async function startOverlay() {
  if (child && !child.killed) {
    log('overlay already running');
    return;
  }
  const dir = projectDir();
  const script = path.join(dir, 'overlay', 'main.py');
  if (!fs.existsSync(script)) {
    const msg = `找不到 ${script}\n请检查 skillWheel.projectDir 设置。`;
    log(msg);
    vscode.window.showErrorMessage(`Skill Wheel: ${msg}`);
    return;
  }
  const python = pythonPath(dir);

  const args = ['-u', script, '--workspace', workspacePath(), '--parent-pid', String(process.pid)];

  log(`spawn: ${python} ${args.join(' ')}`);
  try {
    child = spawn(python, args, {
      cwd: dir,
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
  } catch (err) {
    log(`spawn failed: ${err.message}`);
    vscode.window.showErrorMessage(`Skill Wheel: 启动失败 ${err.message}`);
    child = null;
    return;
  }

  child.stdout.on('data', (b) => log(String(b).trimEnd()));
  child.stderr.on('data', (b) => log(String(b).trimEnd()));
  child.on('error', (err) => {
    log(`overlay error: ${err.message}`);
    child = null;
    updateStatus(false);
    vscode.window.showErrorMessage(
      `Skill Wheel 启动失败：${err.message}\n检查 skillWheel.pythonPath 是否指向装了 PySide6 的 Python。`
    );
  });
  child.on('exit', (code, signal) => {
    log(`overlay exited (code=${code}, signal=${signal})`);
    child = null;
    updateStatus(false);
  });
  updateStatus(true);
}

function stopOverlay() {
  if (!child) {
    updateStatus(false);
    return;
  }
  const pid = child.pid;
  log(`stopping overlay pid=${pid}`);
  try {
    if (process.platform === 'win32') {
      spawn('taskkill', ['/PID', String(pid), '/T', '/F'], { windowsHide: true });
    } else {
      child.kill();
    }
  } catch (err) {
    log(`stop failed: ${err.message}`);
  }
  child = null;
  updateStatus(false);
}

function restartOverlay() {
  stopOverlay();
  setTimeout(() => startOverlay(), 600);
}

function openConfig() {
  try {
    fs.mkdirSync(APP_DIR, { recursive: true });
    if (!fs.existsSync(CONFIG_PATH)) {
      vscode.window.showInformationMessage(
        `首次运行后配置文件会出现在 ${CONFIG_PATH}，可先启动一次 overlay。`
      );
    }
  } catch (err) {
    log(`config dir error: ${err.message}`);
  }
  const uri = vscode.Uri.file(CONFIG_PATH);
  vscode.workspace.openTextDocument(uri).then(
    (doc) => vscode.window.showTextDocument(doc),
    () => vscode.window.showInformationMessage(`配置文件不存在：${CONFIG_PATH}`)
  );
}

function activate(context) {
  output = vscode.window.createOutputChannel('Skill Wheel');
  context.subscriptions.push(output);

  statusItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusItem.command = 'skillWheel.toggle';
  context.subscriptions.push(statusItem);

  context.subscriptions.push(
    vscode.commands.registerCommand('skillWheel.start', () => startOverlay()),
    vscode.commands.registerCommand('skillWheel.stop', () => stopOverlay()),
    vscode.commands.registerCommand('skillWheel.restart', () => restartOverlay()),
    vscode.commands.registerCommand('skillWheel.toggle', () => {
      if (child) stopOverlay(); else startOverlay();
    }),
    vscode.commands.registerCommand('skillWheel.openConfig', () => openConfig()),
    vscode.commands.registerCommand('skillWheel.showLogs', () => output.show(true))
  );

  updateStatus(false);
  if (vscode.workspace.getConfiguration('skillWheel').get('autoStart', true)) {
    startOverlay();
  }

  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration('skillWheel.showStatusBar')) updateStatus(!!child);
      if (e.affectsConfiguration('skillWheel.projectDir') ||
          e.affectsConfiguration('skillWheel.pythonPath')) {
        log('path settings changed — run "Skill Wheel: Restart overlay"');
      }
    })
  );

  log('Skill Wheel extension activated');
}

function deactivate() {
  stopOverlay();
}

module.exports = { activate, deactivate };
