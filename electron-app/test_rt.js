const { createClient } = require('@supabase/supabase-js');
const supabase = createClient('http://localhost:54321', 'sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH');
let n = 0;
const ch = supabase.channel('test');
ch.on('postgres_changes', { event: '*', schema: 'public', table: 'ideas' }, (p) => {
  n++;
  console.log(`[EVENT ${n}] ${p.eventType} - ${p.new?.title || p.old?.id || '?'}`);
});
ch.subscribe((status, err) => {
  console.log(`[STATUS] ${status}${err ? ' ERR: '+err.message : ''}`);
  if (status === 'SUBSCRIBED') {
    setTimeout(() => { console.log(`[DONE] ${n} events`); process.exit(0); }, 10000);
  } else if (status === 'CHANNEL_ERROR' || status === 'TIMED_OUT' || status === 'CLOSED') {
    process.exit(1);
  }
});
setTimeout(() => { console.log('[OVERALL TIMEOUT]'); process.exit(1); }, 15000);
