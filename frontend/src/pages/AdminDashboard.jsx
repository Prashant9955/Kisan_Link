import { useCallback, useEffect, useState } from 'react';
import api, { getApiError } from '../api/api';

const AdminDashboard = () => {
  const [stats, setStats] = useState({});
  const [mandis, setMandis] = useState([]);
  const [transporters, setTransporters] = useState([]);
  const [warehouses, setWarehouses] = useState([]);
  const [disputes, setDisputes] = useState([]);
  const [m, setM] = useState({});
  const [tr, setTr] = useState({});
  const [w, setW] = useState({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState('');
  const [msg, setMsg] = useState('');

  const load = useCallback(async (manual = false) => {
    if (manual) setRefreshing(true);
    try {
      const [a, b, c, d, e] = await Promise.all([
        api.get('/admin/dashboard'),
        api.get('/admin/mandis'),
        api.get('/admin/transporters'),
        api.get('/admin/disputes'),
        api.get('/admin/warehouses'),
      ]);
      setStats(a.data || {});
      setMandis(Array.isArray(b.data) ? b.data : []);
      setTransporters(Array.isArray(c.data) ? c.data : []);
      setDisputes(Array.isArray(d.data) ? d.data : []);
      setWarehouses(Array.isArray(e.data) ? e.data : []);
      setError('');
    } catch (e) {
      setError(getApiError(e, 'Admin data could not be loaded.'));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const addM = async (e) => {
    e.preventDefault(); setError(''); setMsg('');
    try {
      await api.post('/admin/mandis', {
        ...m, longitude: Number(m.longitude), latitude: Number(m.latitude),
      });
      setM({}); setMsg('Mandi added.'); await load();
    } catch (e) { setError(getApiError(e, 'Mandi could not be added.')); }
  };

  const addT = async (e) => {
    e.preventDefault(); setError(''); setMsg('');
    try {
      await api.post('/admin/transporters', {
        ...tr,
        baseRatePerKm: Number(tr.baseRatePerKm || 18),
        minFare: Number(tr.minFare || 250),
      });
      setTr({}); setMsg('Transporter added.'); await load();
    } catch (e) { setError(getApiError(e, 'Transporter could not be added.')); }
  };

  const addW = async (e) => {
    e.preventDefault(); setError(''); setMsg('');
    const capacity = Number(w.capacity);
    const availableCapacity = w.availableCapacity === '' || w.availableCapacity === undefined
      ? capacity
      : Number(w.availableCapacity);
    try {
      await api.post('/admin/warehouses', {
        ...w,
        capacity,
        availableCapacity,
        costPerUnit: Number(w.costPerUnit || 0),
        active: true,
      });
      setW({}); setMsg('Warehouse added successfully.'); await load();
    } catch (e) { setError(getApiError(e, 'Warehouse could not be added.')); }
  };

  const del = async (path, id) => {
    setError(''); setMsg('');
    try { await api.delete(`${path}/${id}`); setMsg('Deleted successfully.'); await load(); }
    catch (e) { setError(getApiError(e, 'Delete failed.')); }
  };

  const resolve = async (dispute, status) => {
    setError(''); setMsg('');
    try {
      await api.put(`/admin/disputes/${dispute._id}`, {
        status,
        resolution: status === 'resolved' ? 'Resolved by admin after review' : 'Moved to review',
      });
      setMsg('Dispute updated.'); await load();
    } catch (e) { setError(getApiError(e, 'Dispute update failed.')); }
  };

  const cards = [
    ['Users', stats.users, '👥'], ['Crops', stats.crops, '🌾'],
    ['Orders', stats.orders, '📦'], ['Bids', stats.bids, '🤝'],
    ['Mandis', stats.mandis, '📍'], ['Open disputes', stats.openDisputes, '🛡️'],
    ['Payments', stats.successfulPayments, '💳'],
    ['Order value', `₹${stats.grossOrderValue || 0}`, '₹'],
  ];

  return (
    <div className="page-shell">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <span className="eyebrow">CONTROL CENTER</span>
          <h1 className="text-4xl font-display font-semibold mt-2">Platform administration</h1>
          <p className="text-ink-soft mt-2">Manage market infrastructure, storage, logistics partners and disputes.</p>
        </div>
        <button onClick={() => load(true)} disabled={refreshing} className="btn-secondary">
          {refreshing ? 'Refreshing…' : '⟳ Refresh dashboard'}
        </button>
      </div>

      {error && <div className="mt-5 rounded-2xl bg-red-50 border border-red-200 text-red-700 p-4 text-sm">⚠️ {error}</div>}
      {msg && <div className="mt-5 rounded-2xl bg-forest/5 border border-forest/15 text-forest p-4 text-sm">✓ {msg}</div>}

      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3 mt-8">
          {cards.map((_, i) => <div key={i} className="h-24 rounded-2xl bg-white border border-line animate-pulse" />)}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3 mt-8">
          {cards.map(([key, value, icon]) => (
            <div key={key} className="soft-card p-4">
              <div className="text-xl">{icon}</div>
              <div className="text-xs text-ink-soft mt-2">{key}</div>
              <div className="text-xl font-bold mt-1">{value ?? '—'}</div>
            </div>
          ))}
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-6 mt-8">
        <section className="soft-card p-6">
          <h2 className="font-display text-xl font-semibold">Mandi directory</h2>
          <p className="text-xs text-ink-soft mt-1">Official GIS market points.</p>
          <form onSubmit={addM} className="grid grid-cols-2 gap-2 mt-5">
            {[
              ['name', 'Name'], ['district', 'District'], ['state', 'State'],
              ['longitude', 'Longitude'], ['latitude', 'Latitude'],
            ].map(([key, placeholder]) => (
              <input key={key} required placeholder={placeholder} value={m[key] || ''}
                onChange={(e) => setM({ ...m, [key]: e.target.value })} className="field" />
            ))}
            <button className="btn-primary col-span-2">+ Add mandi</button>
          </form>
          <div className="mt-6 space-y-2 max-h-64 overflow-auto">
            {mandis.map((item) => (
              <div key={item._id} className="flex justify-between items-center border-b border-line py-3 text-sm">
                <span><b>{item.name}</b><span className="text-ink-soft"> · {item.district}, {item.state}</span></span>
                <button onClick={() => del('/admin/mandis', item._id)} className="text-red-600 hover:underline">Delete</button>
              </div>
            ))}
          </div>
        </section>

        <section className="soft-card p-6">
          <h2 className="font-display text-xl font-semibold">Transporter directory</h2>
          <p className="text-xs text-ink-soft mt-1">Partners used for logistics estimates.</p>
          <form onSubmit={addT} className="grid grid-cols-2 gap-2 mt-5">
            {[
              ['name', 'Name'], ['phone', 'Phone'], ['vehicleType', 'Vehicle type'],
              ['baseRatePerKm', '₹/km'], ['minFare', 'Minimum fare'], ['serviceArea', 'Service area'],
            ].map(([key, placeholder]) => (
              <input key={key} required placeholder={placeholder} value={tr[key] || ''}
                onChange={(e) => setTr({ ...tr, [key]: e.target.value })} className="field" />
            ))}
            <button className="btn-primary col-span-2">+ Add transporter</button>
          </form>
          <div className="mt-6 space-y-2 max-h-64 overflow-auto">
            {transporters.map((item) => (
              <div key={item._id} className="flex justify-between items-center border-b border-line py-3 text-sm">
                <span><b>{item.name}</b><span className="text-ink-soft"> · {item.vehicleType} · ₹{item.baseRatePerKm}/km</span></span>
                <button onClick={() => del('/admin/transporters', item._id)} className="text-red-600 hover:underline">Delete</button>
              </div>
            ))}
          </div>
        </section>

        <section className="soft-card p-6 lg:col-span-2">
          <h2 className="font-display text-xl font-semibold">Warehouse directory</h2>
          <p className="text-xs text-ink-soft mt-1">Storage facilities available for farmers and buyers.</p>
          <form onSubmit={addW} className="grid grid-cols-2 md:grid-cols-3 gap-2 mt-5">
            {[
              ['name', 'Warehouse name', 'text'], ['location', 'Location', 'text'],
              ['capacity', 'Total capacity', 'number'], ['availableCapacity', 'Available capacity', 'number'],
              ['costPerUnit', 'Cost per unit', 'number'], ['contact', 'Contact number', 'text'],
            ].map(([key, placeholder, type]) => (
              <input key={key} required={key !== 'availableCapacity'} type={type}
                min={type === 'number' ? '0' : undefined} step={type === 'number' ? 'any' : undefined}
                placeholder={placeholder} value={w[key] || ''}
                onChange={(e) => setW({ ...w, [key]: e.target.value })} className="field" />
            ))}
            <select value={w.unit || 'quintal'} onChange={(e) => setW({ ...w, unit: e.target.value })} className="field">
              <option value="quintal">Quintal</option><option value="kg">KG</option><option value="ton">Ton</option>
            </select>
            <button className="btn-primary col-span-2 md:col-span-3">+ Add warehouse</button>
          </form>
          <div className="mt-6 grid md:grid-cols-2 gap-3 max-h-80 overflow-auto">
            {warehouses.length === 0 ? <p className="text-sm text-ink-soft">No warehouses added yet.</p> : warehouses.map((item) => (
              <div key={item._id} className="border border-line rounded-2xl p-4 flex justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-semibold break-words">{item.name}</p>
                  <p className="text-sm text-ink-soft mt-1 break-words">{item.location}</p>
                  <p className="text-xs text-ink-soft mt-2">Available: {item.availableCapacity} {item.unit}</p>
                  <p className="text-xs text-ink-soft">Cost: ₹{item.costPerUnit}/{item.unit}</p>
                </div>
                <button onClick={() => del('/admin/warehouses', item._id)} className="text-red-600 hover:underline text-sm shrink-0">Delete</button>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="soft-card p-6 mt-6">
        <div className="flex justify-between items-center">
          <div><h2 className="font-display text-xl font-semibold">Dispute queue</h2><p className="text-xs text-ink-soft mt-1">Review unresolved transaction issues.</p></div>
          <span className="rounded-full bg-gold-soft px-3 py-1 text-xs font-semibold">{disputes.length} open</span>
        </div>
        <div className="mt-5 space-y-3">
          {disputes.length === 0 ? <p className="text-sm text-ink-soft">No disputes.</p> : disputes.map((dispute) => (
            <div key={dispute._id} className="border border-line rounded-2xl p-4 flex flex-col md:flex-row md:justify-between gap-3">
              <div>
                <p className="font-semibold">{dispute.reason} · <span className="capitalize">{dispute.status}</span></p>
                <p className="text-sm text-ink-soft mt-1">{dispute.details}</p>
                <p className="text-xs mt-2 text-ink-soft">Opened by {dispute.openedBy?.name || 'User'}</p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => resolve(dispute, 'under-review')} className="btn-secondary text-sm">Review</button>
                <button onClick={() => resolve(dispute, 'resolved')} className="btn-primary text-sm">Resolve</button>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};

export default AdminDashboard;
