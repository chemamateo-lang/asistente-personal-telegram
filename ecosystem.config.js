module.exports = {
  apps: [{
    name: 'asistente-telegram',
    script: '/home/usuario/bot_refactorizado/venv/bin/python',
    args: '/home/usuario/bot_refactorizado/main.py',
    cwd: '/home/usuario/bot_refactorizado',
    interpreter: 'none',
    env: {
      PYTHONUNBUFFERED: '1'
    },
    watch: false,
    autorestart: true,
    max_restarts: 10,
    min_uptime: '5s',
    restart_delay: 3000,
    log_date_format: 'YYYY-MM-DD HH:mm:ss',
    out_file: '/home/usuario/.pm2/logs/asistente-telegram-out.log',
    error_file: '/home/usuario/.pm2/logs/asistente-telegram-error.log',
    merge_logs: true
  }]
};
