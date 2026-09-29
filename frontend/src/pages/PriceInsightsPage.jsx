import {useState} from 'react'
import api,{getApiError} from '../api/api'

export default function PriceInsightsPage(){
 const [crop,setCrop]=useState('Wheat'),[data,setData]=useState(null),[loading,setLoading]=useState(false),[error,setError]=useState('')
 const load=async()=>{setLoading(true);setError('');try{const r=await api.get(`/forecast/${encodeURIComponent(crop.trim())}`);setData(r.data)}catch(e){setData(null);setError(getApiError(e,'मूल्य पूर्वानुमान उपलब्ध नहीं है।'))}finally{setLoading(false)}}
 const recommendation=()=>{if(!data)return '';if(data.trend==='rising')return 'कीमत बढ़ने की प्रवृत्ति है। यदि भंडारण और नकदी की सुविधा हो तो थोड़ा इंतजार करने पर विचार करें।';if(data.trend==='falling')return 'कीमत घटने की प्रवृत्ति है। उपलब्ध गुणवत्ता, लागत और स्थानीय मांग देखकर जल्दी बिक्री पर विचार करें।';return 'कीमत स्थिर है। खरीदार की पेशकश, भंडारण लागत और तत्काल जरूरत के आधार पर निर्णय लें।'}
 const history=(data?.history||[]).filter(x=>Number.isFinite(x.price))
 const max=Math.max(...history.map(x=>x.price),1),min=Math.min(...history.map(x=>x.price),0)
 return <div className="page-shell"><div><span className="eyebrow">बाज़ार विश्लेषण</span><h1 className="text-4xl font-display font-semibold mt-2">उन्नत मूल्य ट्रेंड और बिक्री सुझाव</h1><p className="text-ink-soft mt-2">सरकारी बाजार डेटा से ट्रेंड देखें। यह सुझाव केवल सहायक अनुमान है, गारंटी नहीं।</p></div>
 <div className="soft-card p-4 mt-6 flex flex-col sm:flex-row gap-3"><input className="field" value={crop} onChange={e=>setCrop(e.target.value)} placeholder="फसल का नाम"/><button className="btn-primary" onClick={load} disabled={loading||!crop.trim()}>{loading?'जाँच जारी…':'ट्रेंड देखें'}</button></div>
 {error&&<div className="mt-4 rounded-2xl bg-red-50 text-red-700 px-4 py-3">{error}</div>}
 {data&&<><div className="grid md:grid-cols-3 gap-4 mt-6"><div className="soft-card p-4"><div className="text-ink-soft text-sm">अंतिम मॉडल कीमत</div><div className="text-2xl font-bold">₹{data.last_price}</div></div><div className="soft-card p-4"><div className="text-ink-soft text-sm">अनुमानित कीमत</div><div className="text-2xl font-bold">₹{data.predicted_price}</div></div><div className="soft-card p-4"><div className="text-ink-soft text-sm">रुझान</div><div className="text-2xl font-bold">{data.trend==='rising'?'बढ़ता हुआ':data.trend==='falling'?'घटता हुआ':'स्थिर'}</div></div></div>
 <div className="soft-card p-5 mt-6"><h2 className="text-xl font-semibold">ऐतिहासिक कीमत चार्ट</h2><div className="mt-4 flex items-end gap-1 h-52 border-b border-l border-line p-2">{history.map((x,i)=><div key={i} title={`${x.date||'तिथि'}: ₹${x.price}`} className="flex-1 bg-forest/70 rounded-t" style={{height:`${Math.max(4,((x.price-min)/Math.max(1,max-min))*100)}%`}}/> )}</div><p className="text-xs text-ink-soft mt-2">हर स्तंभ एक उपलब्ध बाजार observation दर्शाता है।</p></div>
 <div className="soft-card p-5 mt-6"><h2 className="text-xl font-semibold">बिक्री-विंडो सुझाव</h2><p className="mt-2 text-ink-soft">{recommendation()}</p><p className="text-xs text-ink-soft mt-3">आधार: {data.observations} observations और R² {data.r2}. वास्तविक निर्णय में गुणवत्ता, परिवहन, भंडारण और स्थानीय मांग भी देखें।</p></div></>}
 </div>
}
