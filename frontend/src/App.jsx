// @ts-nocheck
import React, { useState, useMemo, useEffect, useCallback } from "react";
import { AreaChart, Area, ResponsiveContainer } from "recharts";
import {
  Leaf, Wheat, Warehouse, Truck, TrendingUp, TrendingDown, Clock, ChevronRight,
  X, Phone, MapPin, Plus, LogOut, ShoppingCart, PackageCheck, CheckCircle2,
  AlertTriangle, History as HistoryIcon, User, ArrowLeft, IndianRupee, Sprout,
  Home as HomeIcon, Star, Building2, Minus, ChevronDown, Eye, EyeOff,
  RefreshCw, Bell, Settings, Shield, HelpCircle, ChevronUp, Sun, Moon
} from "lucide-react";

/* ─────────────────────────────────────────────────────────────────────────── */
/* Theme CSS injected into <head>                                               */
/* ─────────────────────────────────────────────────────────────────────────── */

const THEME_STYLE = `
  :root[data-theme="dark"] {
    --bg-page:      #000000;
    --bg-card:      rgba(24,24,27,0.7);
    --bg-input:     #18181b;
    --bg-nav:       rgba(0,0,0,0.92);
    --bg-chip:      #27272a;
    --border:       #3f3f46;
    --border-faint: #27272a;
    --text-primary: #f4f4f5;
    --text-sub:     #71717a;
    --text-muted:   #52525b;
    --divider:      #27272a;
    --shadow:       0 4px 24px rgba(0,0,0,0.6);
  }
  :root[data-theme="light"] {
    --bg-page:      #f8fafc;
    --bg-card:      rgba(255,255,255,0.9);
    --bg-input:     #ffffff;
    --bg-nav:       rgba(248,250,252,0.95);
    --bg-chip:      #f1f5f9;
    --border:       #cbd5e1;
    --border-faint: #e2e8f0;
    --text-primary: #0f172a;
    --text-sub:     #64748b;
    --text-muted:   #94a3b8;
    --divider:      #e2e8f0;
    --shadow:       0 4px 24px rgba(0,0,0,0.08);
  }

  /* Base resets driven by theme vars */
  body { background: var(--bg-page); color: var(--text-primary); }
  .t-page   { background: var(--bg-page); }
  .t-card   { background: var(--bg-card); border-color: var(--border-faint); }
  .t-input  { background: var(--bg-input); border-color: var(--border); color: var(--text-primary); }
  .t-input::placeholder { color: var(--text-muted); }
  .t-input:focus { border-color: #10b981; box-shadow: 0 0 0 2px rgba(16,185,129,0.2); }
  .t-nav    { background: var(--bg-nav); border-color: var(--border-faint); }
  .t-chip   { background: var(--bg-chip); }
  .t-border { border-color: var(--border-faint); }
  .t-divide > * + * { border-top: 1px solid var(--divider); }
  .t-text   { color: var(--text-primary); }
  .t-sub    { color: var(--text-sub); }
  .t-muted  { color: var(--text-muted); }
  .t-shadow { box-shadow: var(--shadow); }

  /* scrollbar hide */
  .scrollbar-hide::-webkit-scrollbar { display:none; }
  .scrollbar-hide { -ms-overflow-style:none; scrollbar-width:none; }
`;

function injectThemeStyle() {
  if (document.getElementById("ks-theme")) return;
  const el = document.createElement("style");
  el.id = "ks-theme";
  el.textContent = THEME_STYLE;
  document.head.appendChild(el);
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Static reference data                                                        */
/* ─────────────────────────────────────────────────────────────────────────── */

const KA_DISTRICTS = [
  "Bagalkot","Ballari","Belagavi","Bengaluru Rural","Bengaluru Urban","Bidar",
  "Chamarajanagar","Chikkaballapur","Chikkamagaluru","Chitradurga",
  "Dakshina Kannada","Davanagere","Dharwad","Gadag","Hassan","Haveri",
  "Kalaburagi","Kodagu","Kolar","Koppal","Mandya","Mysuru","Raichur",
  "Ramanagara","Shivamogga","tumkur","Udupi","Uttara Kannada","Vijayapura","Yadgir",
];

// Adjacency map for Karnataka districts — used to prioritise nearby cold storages
const KA_NEIGHBORS = {
  "Bagalkot":         ["Vijayapura","Bidar","Gadag","Dharwad","Belagavi","Koppal","Raichur"],
  "Ballari":          ["Koppal","Raichur","Davanagere","Chitradurga","Kolar"],
  "Belagavi":         ["Dharwad","Gadag","Bagalkot","Vijayapura","Haveri","Uttara Kannada"],
  "Bengaluru Rural":  ["Bengaluru Urban","Ramanagara","tumkur","Chikkaballapur","Kolar"],
  "Bengaluru Urban":  ["Bengaluru Rural","Ramanagara","tumkur","Chikkaballapur","Kolar"],
  "Bidar":            ["Kalaburagi","Yadgir","Raichur"],
  "Chamarajanagar":   ["Mysuru","Kodagu"],
  "Chikkaballapur":   ["Bengaluru Rural","Bengaluru Urban","Kolar","tumkur"],
  "Chikkamagaluru":   ["Hassan","Shivamogga","Dakshina Kannada","Udupi","Kodagu","Davanagere"],
  "Chitradurga":      ["Davanagere","tumkur","Shivamogga","Ballari","Chikkamagaluru"],
  "Dakshina Kannada": ["Udupi","Kodagu","Chikkamagaluru"],
  "Davanagere":       ["Shivamogga","Chitradurga","Ballari","Haveri","Koppal","Chikkamagaluru"],
  "Dharwad":          ["Gadag","Haveri","Belagavi","Uttara Kannada"],
  "Gadag":            ["Dharwad","Haveri","Koppal","Bagalkot","Belagavi"],
  "Hassan":           ["Chikkamagaluru","Mandya","Mysuru","Kodagu","Shivamogga","tumkur"],
  "Haveri":           ["Dharwad","Gadag","Davanagere","Shivamogga","Uttara Kannada"],
  "Kalaburagi":       ["Bidar","Yadgir","Raichur","Vijayapura"],
  "Kodagu":           ["Hassan","Mysuru","Dakshina Kannada","Chikkamagaluru","Chamarajanagar"],
  "Kolar":            ["Bengaluru Urban","Bengaluru Rural","Chikkaballapur","Ballari"],
  "Koppal":           ["Ballari","Raichur","Gadag","Davanagere","Bagalkot"],
  "Mandya":           ["Mysuru","Hassan","Ramanagara","tumkur"],
  "Mysuru":           ["Mandya","Hassan","Chamarajanagar","Kodagu","Ramanagara"],
  "Raichur":          ["Koppal","Ballari","Kalaburagi","Yadgir","Bagalkot","Bidar"],
  "Ramanagara":       ["Bengaluru Urban","Bengaluru Rural","Mandya","Mysuru","tumkur"],
  "Shivamogga":       ["Davanagere","Chikkamagaluru","Hassan","Haveri","Uttara Kannada","Chitradurga"],
  "tumkur":         ["Bengaluru Rural","Bengaluru Urban","Chikkaballapur","Chitradurga","Hassan","Mandya","Ramanagara"],
  "Udupi":            ["Dakshina Kannada","Chikkamagaluru","Uttara Kannada"],
  "Uttara Kannada":   ["Dharwad","Haveri","Shivamogga","Udupi","Belagavi"],
  "Vijayapura":       ["Bagalkot","Kalaburagi","Bidar","Yadgir"],
  "Yadgir":           ["Kalaburagi","Raichur","Bidar","Vijayapura"],
};

function districtTier(farmerDistrict, storageDistrict) {
  const fd = (farmerDistrict || "").trim();
  const sd = (storageDistrict || "").trim();
  if (!fd || !sd) return 3;
  if (fd.toLowerCase() === sd.toLowerCase()) return 0; // same district
  const neighbors = KA_NEIGHBORS[fd] || [];
  if (neighbors.some(n => n.toLowerCase() === sd.toLowerCase())) return 1; // adjacent
  return 2; // farther
}

const CROP_CATALOG = [
  { name:"Tomato",      emoji:"🍅", basePrice:1200 },
  { name:"Onion",       emoji:"🧅", basePrice:1800 },
  { name:"Potato",      emoji:"🥔", basePrice:1100 },
  { name:"Mango",       emoji:"🥭", basePrice:3200 },
  { name:"Banana",      emoji:"🍌", basePrice:1500 },
  { name:"Cabbage",     emoji:"🥬", basePrice:900  },
  { name:"Cauliflower", emoji:"🥦", basePrice:1300 },
  { name:"Carrot",      emoji:"🥕", basePrice:1600 },
  { name:"Beans",       emoji:"🫘", basePrice:4200 },
  { name:"Grapes",      emoji:"🍇", basePrice:5500 },
];

const VEHICLES = [
  "Mini Truck / Tata Ace","Medium Truck (407)","Large Truck (14-wheeler)",
  "Refrigerated Van","Refrigerated Truck","Custom / Other",
];

/*const BUYER_NAMES    = ["Kaveri Agro Traders","Sri Lakshmi Mandi","Bengaluru FreshMart Co.","Nandi Exports","Deccan Agri Buyers","KA Fresh Wholesale"];
const STORAGE_NAMES  = ["AgroFreeze","ColdLine Storage","FarmKeep Warehousing","Annapurna Cold Chain","Karnataka CoolStore"];
const TRANSPORT_NAMES= ["Raju Transport","Karnataka Roadlines","Swift Farm Logistics","Mallige Carriers","Cauvery Agri Movers"];*/

const ALL_ROLES = [
  { key:"farmer",    label:"Farmer",                Icon:Sprout,   color:"text-emerald-400", bg:"bg-emerald-500/10" },
  { key:"storage",   label:"Cold Storage Operator", Icon:Warehouse,color:"text-amber-400",   bg:"bg-amber-500/10"   },
  { key:"transport", label:"Transporter",           Icon:Truck,    color:"text-sky-400",     bg:"bg-sky-500/10"     },
  { key:"trader",    label:"Trader / Buyer",        Icon:Building2,color:"text-violet-400",  bg:"bg-violet-500/10"  },
];

/* ─────────────────────────────────────────────────────────────────────────── */
/* Bridge / backend                                                             */
/* ─────────────────────────────────────────────────────────────────────────── */

const BRIDGE = {
  serverID:   "247366f9-f180-4c54-927d-0c008d07fff4-c8786a26-5320-439b-b0f7-aff6d1655525",
  forumID:    "d733e328-8fc4-4601-ac4f-691530131cc2",
  templateID: "65fe64c1-6227-c6e8-276b-1a24674196cb",
  flows: {
    farmer:    { id:"NewFarmerTemplate_FarmerFlow",        fid:"e5eb2da9-7c55-eb1e-a474-b44a65243a12" },
    storage:   { id:"NewFarmerTemplate_ColdStorageInput",  fid:"764f14fe-be57-bc32-0a35-57632fc277e5" },
    transport: { id:"NewFarmerTemplate_TransportInput",    fid:"d52ab85c-9f05-2e90-01af-8b8f53cdaf25" },
    trader:    { id:"NewFarmerTemplate_TraderInput",       fid:"3443a005-945f-b26b-d2bc-4cb85c12100f" },
    booking:  { id:"NewFarmerTemplate_Booking",       fid:"3443a005-945f-b26b-d2bc-4cb85c12100f" },
    accountInput: { id:"NewFarmerTemplate_AccountInput",   fid: "0bcf020e-6219-fadc-585f-35cde65acac8" },
  },

  fields: {
  accountInput:{
      mobile: "NewFarmerTemplate_AccountInput_Main-0bcf020e-6219-fadc-585f-35cde65acac8_7",
      passHash: "NewFarmerTemplate_AccountInput_Main-0bcf020e-6219-fadc-585f-35cde65acac8_8",
      name: "NewFarmerTemplate_AccountInput_Main-0bcf020e-6219-fadc-585f-35cde65acac8_9",
      district: "NewFarmerTemplate_AccountInput_Main-0bcf020e-6219-fadc-585f-35cde65acac8_10",
      role: "NewFarmerTemplate_AccountInput_Main-0bcf020e-6219-fadc-585f-35cde65acac8_11",
      activeRoles: "NewFarmerTemplate_AccountInput_Main-0bcf020e-6219-fadc-585f-35cde65acac8_12"
    },
    farmer: {
      name:"NewFarmerTemplate_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_11",
      phone:"NewFarmerTemplate_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_12",
      district:"NewFarmerTemplate_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_13",
      crop:"NewFarmerTemplate_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_15",
      qty:"NewFarmerTemplate_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_16",
      days:"NewFarmerTemplate_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_17",
      village:"NewFarmerTemplate_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_22",
      prefStorage:"NewFarmerTemplate_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_23",
      notes:"NewFarmerTemplate_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_24",
      confirm:"NewFarmerTemplate_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_25",
    },
    storage: {
      facility:"NewFarmerTemplate_ColdStorageInput_Main-764f14fe-be57-bc32-0a35-57632fc277e5_14",
      operator:"NewFarmerTemplate_ColdStorageInput_Main-764f14fe-be57-bc32-0a35-57632fc277e5_15",
      phone:"NewFarmerTemplate_ColdStorageInput_Main-764f14fe-be57-bc32-0a35-57632fc277e5_16",
      district:"NewFarmerTemplate_ColdStorageInput_Main-764f14fe-be57-bc32-0a35-57632fc277e5_17",
      address:"NewFarmerTemplate_ColdStorageInput_Main-764f14fe-be57-bc32-0a35-57632fc277e5_18",
      cap:"NewFarmerTemplate_ColdStorageInput_Main-764f14fe-be57-bc32-0a35-57632fc277e5_19",
      fromDays:"NewFarmerTemplate_ColdStorageInput_Main-764f14fe-be57-bc32-0a35-57632fc277e5_20",
      duration:"NewFarmerTemplate_ColdStorageInput_Main-764f14fe-be57-bc32-0a35-57632fc277e5_21",
      crops:"NewFarmerTemplate_ColdStorageInput_Main-764f14fe-be57-bc32-0a35-57632fc277e5_22",
      rate:"NewFarmerTemplate_ColdStorageInput_Main-764f14fe-be57-bc32-0a35-57632fc277e5_23",
      notes:"NewFarmerTemplate_ColdStorageInput_Main-764f14fe-be57-bc32-0a35-57632fc277e5_25",
      confirm:"NewFarmerTemplate_ColdStorageInput_Main-764f14fe-be57-bc32-0a35-57632fc277e5_26",
    },
    transport: {
      name:"NewFarmerTemplate_TransportInput_Main-0255c7f2-7283-531e-933f-4bc60c911124_15",
      driver:"NewFarmerTemplate_TransportInput_Main-0255c7f2-7283-531e-933f-4bc60c911124_16",
      phone:"NewFarmerTemplate_TransportInput_Main-0255c7f2-7283-531e-933f-4bc60c911124_17",
      district:"NewFarmerTemplate_TransportInput_Main-0255c7f2-7283-531e-933f-4bc60c911124_18",
      vehicle:"NewFarmerTemplate_TransportInput_Main-0255c7f2-7283-531e-933f-4bc60c911124_19",
      cap:"NewFarmerTemplate_TransportInput_Main-0255c7f2-7283-531e-933f-4bc60c911124_20",
      refrig:"NewFarmerTemplate_TransportInput_Main-0255c7f2-7283-531e-933f-4bc60c911124_21",
      fromDays:"NewFarmerTemplate_TransportInput_Main-0255c7f2-7283-531e-933f-4bc60c911124_22",
      avDays:"NewFarmerTemplate_TransportInput_Main-0255c7f2-7283-531e-933f-4bc60c911124_23",
      maxDist:"NewFarmerTemplate_TransportInput_Main-0255c7f2-7283-531e-933f-4bc60c911124_24",
      rate:"NewFarmerTemplate_TransportInput_Main-0255c7f2-7283-531e-933f-4bc60c911124_25",
      opDists:"NewFarmerTemplate_TransportInput_Main-0255c7f2-7283-531e-933f-4bc60c911124_26",
      notes:"NewFarmerTemplate_TransportInput_Main-0255c7f2-7283-531e-933f-4bc60c911124_27",
      confirm:"NewFarmerTemplate_TransportInput_Main-0255c7f2-7283-531e-933f-4bc60c911124_28",
    },
    trader: {
      company:"NewFarmerTemplate_TraderInput_Main-5de6720a-8239-caa3-6372-3cdb5eadeeea_7",
      phone:"NewFarmerTemplate_TraderInput_Main-5de6720a-8239-caa3-6372-3cdb5eadeeea_8",
      district:"NewFarmerTemplate_TraderInput_Main-5de6720a-8239-caa3-6372-3cdb5eadeeea_9",
      crops:"NewFarmerTemplate_TraderInput_Main-5de6720a-8239-caa3-6372-3cdb5eadeeea_10",
      buyDists:"NewFarmerTemplate_TraderInput_Main-5de6720a-8239-caa3-6372-3cdb5eadeeea_11",
      confirm:"NewFarmerTemplate_TraderInput_Main-5de6720a-8239-caa3-6372-3cdb5eadeeea_12",
    },
    booking: {
      FarmerID:"NewFarmerTemplate_Booking_Main-049205e6-d4e3-6647-473e-c79ea658b977_2",
      SellStore:"NewFarmerTemplate_Booking_Main-049205e6-d4e3-6647-473e-c79ea658b977_5",
      StorageDays:"NewFarmerTemplate_Booking_Main-049205e6-d4e3-6647-473e-c79ea658b977_6",
      Confirm: "NewFarmerTemplate_Booking_Main-049205e6-d4e3-6647-473e-c79ea658b977_8",
    }
  },
};

/* ─────────────────────────────────────────────────────────────────────────── */
/* Persistent storage helpers                                                   */
/* ─────────────────────────────────────────────────────────────────────────── */
const API = "https://krishisetu-backend.onrender.com";
const STORAGE_VERSION = "v3";
function userKey(mobile, kind) { return `ks_${STORAGE_VERSION}_${mobile}_${kind}`; }

async function loadUserData(mobile) {
  console.log("LOAD USER DATA", mobile);

  if (!mobile) {
    console.trace("loadUserData called with undefined mobile");
    console.error("loadUserData called with undefined mobile");
    return {
      crops: [],
      activity: [],
      profile: null,
      bizData: {}
    };
  }

  const res = await fetch(
    `${API}/loadUserData/${mobile}`
  );

  return await res.json();
}

async function saveUserData(mobile, kind, value) {

  console.log("SAVE USER DATA", {
    mobile,
    kind,
    value
  });
  if (!mobile) {
    console.trace("saveUserData called with undefined mobile");
    console.error("mobile is undefined");
    return;
  }
  await fetch(
    "http://localhost:5000/saveUserData",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        mobile,
        kind,
        value
      })
    }
  );
}

/*
async function loadUsers() {

  const res = await fetch(
    "http://localhost:5000/loadUsers"
  );

  return await res.json();
}

async function saveUsers(users) {

  await fetch(
    "http://localhost:5000/saveUsers",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(users)
    }
  );
}
*/


/* ─────────────────────────────────────────────────────────────────────────── */
/* Helpers                                                                      */
/* ─────────────────────────────────────────────────────────────────────────── */

function hashSeed(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = (h * 31 + str.charCodeAt(i)) >>> 0;
  return h || 1;
}
function seededRand(seed) {
  let s = seed % 2147483647;
  if (s <= 0) s += 2147483646;
  return () => { s = (s * 16807) % 2147483647; return (s - 1) / 2147483646; };
}
function b64(text) {
  try { return btoa(unescape(encodeURIComponent(String(text)))); } catch { return btoa(String(text)); }
}
async function bridgePost(url, payload) {
  const fd = new FormData();
  fd.append("Data", JSON.stringify(payload));
  const res  = await fetch(url, { method:"POST", body:fd });
  const text = await res.text();
  if (!text || !text.trim()) throw new Error("Empty response");
  try { return JSON.parse(text); } catch { return { raw: text }; }
}
async function sendToFlow(flowType, fieldValues) {
  const flow   = BRIDGE.flows[flowType];
  const fields = BRIDGE.fields[flowType];
  const payload = {};
  for (const [key, fieldID] of Object.entries(fields)) {
    const val = fieldValues[key];
    if (val !== undefined && val !== null && val !== "") payload[fieldID] = b64(String(val));
  }
  console.log("FLOW TYPE =", flowType);
  console.log("FIELDS =", fields);
  console.log("PAYLOAD =", payload);
  const body = {
    ForumID:           BRIDGE.forumID,
    SessionID:         "487ba01b-d94c-4e22-84dc-4316e65854e2",
    MACAddress:        "Bridge-Web",
    UserName:          "@keerthana",
    Time:              String(Date.now()),
    ScheduledDateTime: "now",
    ScheduledBoolean:  false,
    FlowID:            flow.id,
    EnableChat:        false,
    FlowType:          "Custom",
    BridgeForward:     false,
    TemplateID:        BRIDGE.templateID,
    TextCount:         1,
    ImageCount:        0,
    InvoiceID:         "",
    DocumentCount:     0,
    User:              true,
    VideoCount:        0,
    HiddenFlow:        false,
    TempBridgeId:      (crypto.randomUUID ? crypto.randomUUID() : String(Math.random())),
    FID:               flow.fid,
    ServerID:          BRIDGE.serverID,
    SentTo:            "1",
    ReplyBridgeID:     "",
    [flow.id]:         payload,
  };
  const result = await bridgePost("https://fs.cosmitude.com/saveForumBridges2", body);
  console.log("BRIDGE RESPONSE",result);
  return result;
}

function cropMeta(name) {
  return CROP_CATALOG.find((c) => c.name === name) || { name, emoji:"🌱", basePrice:1500 };
}
function fmtINR(n) { return "₹" + Math.round(n).toLocaleString("en-IN"); }

// Pulls a plain number out of a free-text rate string coming back from the
// advisory (e.g. "₹150/MT/day" or "150 per MT per day") so it can be used in
// cost maths. Falls back to 0 if nothing numeric is found.
function parseRateValue(rateStr) {
  if (!rateStr) return 0;
  const match = String(rateStr).match(/[\d,]+(\.\d+)?/);
  if (!match) return 0;
  return Number(match[0].replace(/,/g, "")) || 0;
}

async function getTransportBookings() {

  const res = await fetch(
    "http://localhost:5000/loadTransportBookings"
  );

  return await res.json();
}

async function saveTransportBookings(bookings) {

  await fetch(
    "http://localhost:5000/saveTransportBookings",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(bookings)
    }
  );
}


async function isTransportAvailable(
  transporter,
  selectedDate
) {
  const bookings = await getTransportBookings();

  const selected = new Date(selectedDate);

  return !bookings.some((b) => {
    if (b.transporter !== transporter.name)
      return false;

    const start = new Date(b.startDate);
    const end = new Date(b.endDate);

    return selected >= start &&
           selected <= end;
  });
}

function buildAdvisory(entry) {
  const meta  = cropMeta(entry.name);
  const rand  = seededRand(hashSeed(entry.id));
  let price   = meta.basePrice * (0.9 + rand() * 0.2);
  const trend = [];
  for (let i = 0; i < 10; i++) {
    price = Math.max(200, price * (1 + (rand() - 0.46) * 0.05));
    trend.push({ i, p: Math.round(price) });
  }
  const changePct = ((trend[9].p - trend[0].p) / trend[0].p) * 100;
  let verdict, reason;
  if (changePct > 4) {
    verdict = "sell";
    reason  = `${entry.name} is fetching ${changePct.toFixed(1)}% more than 10 days ago in ${entry.district} — demand is strong right now.`;
  } else if (changePct < -3) {
    verdict = "store";
    reason  = `${entry.name} prices have slipped ${Math.abs(changePct).toFixed(1)}% lately. Holding in cold storage can protect quality until rates recover.`;
  } else {
    verdict = "hold";
    reason  = `${entry.name} prices are stable in ${entry.district}. Selling now locks in a fair rate; storing is a safe bet too.`;
  }
  return { price: trend[9].p, changePct, trend, verdict, reason };
}

async function getAllAccounts() {
  const data = await getBridges();

  const admin = data?.ErrorMessage?.Admin || [];
  const user  = data?.ErrorMessage?.User  || [];

  const all = [...admin, ...user]
    .map(r => r?.Bridge || r)
    .filter(Boolean);

  console.log("ALL BRIDGES COUNT =", all.length);
  console.log("ACCOUNT INPUT FID =", BRIDGE.flows.accountInput.fid);

  const found = all.filter(
    b => b.FID === BRIDGE.flows.accountInput.fid
  );

  console.log("FOUND ACCOUNT BRIDGES =", found.length);

  found.forEach((b, i) => {
    try {
      const flow = b[BRIDGE.flows.accountInput.id] || {};
      const rawVal = flow[BRIDGE.fields.accountInput.mobile];

      console.log(
        `ACCOUNT[${i}] raw=`,
        rawVal,
        "decoded=",
        rawVal ? atob(rawVal) : "N/A"
      );
    } catch (e) {
      console.error("Decode error", e);
    }
  });

  return found;
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Real-data marketplace lookups — reads other users' registered bizData        */
/* ─────────────────────────────────────────────────────────────────────────── */
async function getAllStorages(currentMobile) {

  const accounts = await getAllAccounts();
  const results = [];

  for (const mobile of Object.keys(users)) {

    if (mobile === currentMobile)
      continue;

    try {

      const data = await loadUserData(mobile);

      const bd = data.bizData || {};
      const profile = data.profile || null;

      const list = Array.isArray(bd.storage)
        ? bd.storage
        : (bd.storage ? [bd.storage] : []);

      list.forEach((s) =>
        results.push({
          ...s,
          ownerName: profile?.name || "Operator",
          ownerPhone: profile?.mobile || mobile
        })
      );

    } catch (err) {
      console.error(err);
    }
  }

  return results;
}

async function getAllTransporters(currentMobile) {

  const accounts = await getAllAccounts();
  const results = [];

  for (const mobile of Object.keys(users)) {

    if (mobile === currentMobile)
      continue;

    try {

      const data = await loadUserData(mobile);

      const bd = data.bizData || {};
      const profile = data.profile || null;

      const list = Array.isArray(bd.transport)
        ? bd.transport
        : (bd.transport ? [bd.transport] : []);

      list.forEach((t) =>
        results.push({
          ...t,
          ownerName: profile?.name || "Transporter",
          ownerPhone: profile?.mobile || mobile
        })
      );

    } catch (err) {
      console.error(err);
    }
  }

  return results;
}

async function getAllTraders(currentMobile) {

  const accounts = await getAllAccounts();
  const results = [];

  for (const mobile of Object.keys(users)) {

    if (mobile === currentMobile)
      continue;

    try {

      const data = await loadUserData(mobile);

      const bd = data.bizData || {};
      const profile = data.profile || null;

      if (bd.trader) {
        results.push({
          ...bd.trader,
          ownerName: profile?.name || "Trader",
          ownerPhone: profile?.mobile || mobile
        });
      }

    } catch (err) {
      console.error(err);
    }
  }

  return results;
}

async function getBuyerMatches(entry, advisoryPrice, currentMobile) {
  const traders = await getAllTraders(currentMobile);
  if (traders.length === 0) return [];
  const cropLower = entry.name.toLowerCase();
  const matching = traders.filter((t) => {
    const crops = (t.crops || "").toLowerCase();
    return crops.includes("all") || crops.includes(cropLower);
  });
  if (matching.length === 0) return [];
  const rand = seededRand(hashSeed(entry.id + "_buy"));
  return matching.map((t) => ({
    ...t,
    price: Math.round(advisoryPrice * (0.92 + rand() * 0.16)),
  })).sort((a, b) => b.price - a.price);
}

async function getStorageMatches(entry, currentMobile) {
  const storages = await getAllStorages(currentMobile);
  const all = storages.filter((s) => {
    const crops = (s.crops || "").toLowerCase();
    const cropMatch = crops.includes("all") || crops.includes(entry.name.toLowerCase());
    const capOk = !s.cap || Number(s.cap) >= entry.qty;
    return cropMatch && capOk;
  });

  // Sort by: 1) district proximity tier (same=0, adjacent=1, far=2), 2) rate ascending
  all.sort((a, b) => {
    const tierA = districtTier(entry.district, a.district);
    const tierB = districtTier(entry.district, b.district);
    if (tierA !== tierB) return tierA - tierB;
    return Number(a.rate || 99999) - Number(b.rate || 99999);
  });

  // Return only the single best option
  return all.slice(0, 1);
}

async function getTransportMatches(
  entry,
  currentMobile,
  selectedDate
) {

  const transporters =
    await getAllTransporters(currentMobile);

  const results = [];

  for (const t of transporters) {

    const capOk =
      !t.cap ||
      Number(t.cap) >= entry.qty;

    const available =
      await isTransportAvailable(
        t,
        selectedDate
      );

    if (capOk && available)
      results.push(t);
  }

  return results;
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Shared style helpers (theme-aware)                                           */
/* ─────────────────────────────────────────────────────────────────────────── */

const TONE = {
  sell:  { text:"text-emerald-500", bg:"bg-emerald-500/10", border:"border-emerald-500/30", dot:"bg-emerald-400" },
  store: { text:"text-amber-500",   bg:"bg-amber-500/10",   border:"border-amber-500/30",   dot:"bg-amber-400"   },
  hold:  { text:"text-zinc-400",    bg:"bg-zinc-500/10",    border:"border-zinc-500/30",     dot:"bg-zinc-400"    },
};

/* ─────────────────────────────────────────────────────────────────────────── */
/* Primitives                                                                   */
/* ─────────────────────────────────────────────────────────────────────────── */

function VerdictBadge({ verdict }) {
  const tone  = TONE[verdict];
  const label = verdict==="sell" ? "Sell now" : verdict==="store" ? "Store" : "Hold";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border ${tone.border} ${tone.bg} px-2.5 py-1 text-xs font-medium ${tone.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${tone.dot}`} />
      {label}
    </span>
  );
}

function Field({ label, required, children }) {
  return (
    <label className="block mb-3">
      <span className="block text-[11px] font-medium uppercase tracking-wide t-sub mb-1.5">
        {label}{required && <span className="text-rose-400 ml-0.5">*</span>}
      </span>
      {children}
    </label>
  );
}

const inputCls = "t-input w-full rounded-lg border px-3 py-2.5 text-sm outline-none transition focus:outline-none";

function TextInput(props) { return <input {...props} className={inputCls} />; }
function Select({ children, ...props }) {
  return (
    <div className="relative">
      <select {...props} className={inputCls + " appearance-none pr-8"}>{children}</select>
      <ChevronDown className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 h-4 w-4 t-muted" />
    </div>
  );
}
function TextArea(props) { return <textarea {...props} rows={2} className={inputCls + " resize-none"} />; }

function PrimaryButton({ children, className="", loading, ...props }) {
  return (
    <button {...props} className={`w-full rounded-lg bg-emerald-500 text-white font-semibold py-2.5 text-sm transition hover:bg-emerald-400 active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2 ${className}`}>
      {loading && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
      {children}
    </button>
  );
}
function GhostButton({ children, className="", ...props }) {
  return (
    <button {...props} className={`w-full rounded-lg border t-border t-text font-medium py-2.5 text-sm transition hover:opacity-80 active:scale-[0.98] flex items-center justify-center gap-2 ${className}`}>
      {children}
    </button>
  );
}

function Sparkline({ trend, verdict }) {
  const color = verdict==="sell" ? "#10b981" : verdict==="store" ? "#f59e0b" : "#71717a";
  return (
    <div className="h-10 w-20">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={trend} margin={{top:2,right:0,bottom:0,left:0}}>
          <Area type="monotone" dataKey="p" stroke={color} fill={color} fillOpacity={0.18} strokeWidth={2} dot={false} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function Sheet({ title, onClose, children }) {
  const [shown, setShown] = useState(false);
  useEffect(() => { const id = requestAnimationFrame(() => setShown(true)); return () => cancelAnimationFrame(id); }, []);
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className={`t-card t-shadow relative w-full max-w-md max-h-[90vh] overflow-y-auto rounded-t-3xl border-t p-5 pb-8 transition-transform duration-300 ${shown?"translate-y-0":"translate-y-full"}`}>
        <div className="mx-auto mb-4 h-1 w-10 rounded-full bg-zinc-400/30" />
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold t-text">{title}</h3>
          <button onClick={onClose} className="rounded-full p-1.5 t-sub hover:opacity-70 transition"><X className="h-4 w-4" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

function Toast({ message, type="info" }) {
  const base = "fixed bottom-24 left-1/2 -translate-x-1/2 z-[60] rounded-full border px-4 py-2 text-xs shadow-lg backdrop-blur";
  const colors = {
    info:    "bg-zinc-800/90 border-zinc-600 text-zinc-100",
    success: "bg-emerald-900/90 border-emerald-600 text-emerald-100",
    error:   "bg-rose-900/90 border-rose-600 text-rose-100"
  };
  return <div className={`${base} ${colors[type]}`}>{message}</div>;
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Auth screen                                                                  */
/* ─────────────────────────────────────────────────────────────────────────── */

function AuthScreen({ onLogin }) {
  const [mode,      setMode]      = useState("login");
  const [mobile,    setMobile]    = useState("");
  const [pass,      setPass]      = useState("");
  const [name,      setName]      = useState("");
  const [district,  setDistrict]  = useState("");
  const [role,      setRole]      = useState("");
  const [showPass,  setShowPass]  = useState(false);
  const [errs,      setErrs]      = useState({});
  const [loading,   setLoading]   = useState(false);

  function validate() {
    const e = {};
    if (!/^\d{10}$/.test(mobile)) e.mobile = "Enter a valid 10-digit mobile number";
    if (!pass || pass.length < 4)  e.pass   = "Password must be at least 4 characters";
    if (mode === "register") {
      if (!name.trim()) e.name     = "Name is required";
      if (!district)    e.district = "Select your district";
      if (!role)        e.role     = "Select your primary role";
    }
    setErrs(e);
    return Object.keys(e).length === 0;
  }

  async function submit() {
    if (!validate()) return;
    setLoading(true);
    const accounts = await getAllAccounts();

    const account = accounts.find(acc => {
      const flow = acc[BRIDGE.flows.accountInput.id];

      if (!flow) return false;

      try {
        const storedMobile = atob(
          flow[BRIDGE.fields.accountInput.mobile] || ""
        );

        return storedMobile === mobile;
      } catch {
        return false;
      }
    });

    console.log("ACCOUNT FOUND =", account);

    if (mode === "register") {
      const existing = accounts.find(acc => {
        const flow = acc.NewFarmerTemplate_AccountInput;
        if (!flow) return false;
        try {
          return atob(flow[BRIDGE.fields.accountInput.mobile] || "") === mobile;
        } catch { return false; }
      });

      if (existing) {
        setErrs({ mobile: "This number is already registered. Sign in instead." });
        setLoading(false);
        return;
      }

      const profile = {
        mobile, name: name.trim(), district, role,
        activeRoles: [role],
        registeredAt: new Date().toISOString()
      };

      const result = await sendToFlow("accountInput", {
        mobile,
        passHash: pass,
        name: profile.name || "",
        district: profile.district || "",
        role: profile.role || "farmer",
        activeRoles: JSON.stringify(profile.activeRoles || [])
      });

      console.log("ACCOUNT INPUT RESULT =", result);
      await saveUserData(mobile, "profile", profile);
      await saveUserData(mobile, "crops", []);
      await saveUserData(mobile, "activity", []);
      await saveUserData(mobile, "bizdata", {});
      onLogin(profile);

    } else {
    // Login — find account in Bridge
      const record = accounts.find(acc => {
        const flow = account.NewFarmerTemplate_AccountInput;
        console.log("FLOW =", flow);
        console.log(
        "PASSWORD IN BRIDGE =",
        atob(flow[BRIDGE.fields.accountInput.passHash] || "")
        );
        //const flow = acc.NewFarmerTemplate_AccountInput;
        if (!flow) return false;
        try {
          return atob(flow[BRIDGE.fields.accountInput.mobile] || "") === mobile;
        } catch { return false; }
      });

      if (!account) {
        setErrs({ mobile: "Number not registered. Create an account first." });
        setLoading(false);
        return;
      }
      
      const flow = record.NewFarmerTemplate_AccountInput;

      const storedHash = atob(
        flow[BRIDGE.fields.accountInput.passHash] || ""
      );

      if (storedHash !== pass) {
        setErrs({ pass: "Incorrect password." });
        setLoading(false);
        return;
      }

      const data = await loadUserData(mobile);
      const profile = data.profile && Object.keys(data.profile).length > 0
        ? data.profile
        : { mobile, name: "Farmer", district: "", role: "farmer", activeRoles: ["farmer"] };

      onLogin(profile);
    }

    setLoading(false);
  }

  return (
    <div className="flex-1 flex flex-col justify-center px-6 py-8">
      <div className="text-center mb-8">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-500/10 border border-emerald-500/30 shadow-lg shadow-emerald-500/10">
          <Leaf className="h-8 w-8 text-emerald-500" />
        </div>
        <h1 className="text-2xl font-bold tracking-tight bg-gradient-to-r from-emerald-500 to-lime-400 bg-clip-text text-transparent">
          KrishiSetu
        </h1>
        <p className="mt-1 text-sm t-sub">Connecting Karnataka's farmers, storage &amp; transport</p>
      </div>

      <div className="flex rounded-xl t-chip border t-border p-1 mb-5">
        {[["login","Sign in"],["register","Create account"]].map(([key,label]) => (
          <button key={key} onClick={() => { setMode(key); setErrs({}); }}
            className={`flex-1 rounded-lg py-2 text-sm font-medium transition ${mode===key ? "bg-white dark:bg-zinc-800 t-text shadow" : "t-sub"}`}>
            {label}
          </button>
        ))}
      </div>

      <div className="rounded-2xl border t-border t-card p-4">
        {mode === "register" && (
          <>
            <Field label="Your name" required>
              <TextInput placeholder="Ramesh Kumar" value={name} onChange={(e) => setName(e.target.value)} />
              {errs.name && <p className="mt-1 text-xs text-rose-400">{errs.name}</p>}
            </Field>
            <Field label="Home district" required>
              <Select value={district} onChange={(e) => setDistrict(e.target.value)}>
                <option value="">Select district</option>
                {KA_DISTRICTS.map((d) => <option key={d}>{d}</option>)}
              </Select>
              {errs.district && <p className="mt-1 text-xs text-rose-400">{errs.district}</p>}
            </Field>
            <Field label="I am primarily a" required>
              <div className="grid grid-cols-2 gap-2 mt-1">
                {ALL_ROLES.map(({ key, label, Icon, color, bg }) => (
                  <button key={key} type="button" onClick={() => setRole(key)}
                    className={`flex items-center gap-2 rounded-xl border p-3 text-left transition
                      ${role === key ? "border-emerald-500 bg-emerald-500/10" : "border-zinc-300 dark:border-zinc-700 t-card hover:opacity-80"}`}>
                    <div className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg ${bg}`}>
                      <Icon className={`h-4 w-4 ${color}`} />
                    </div>
                    <span className="text-xs font-medium t-text leading-tight">{label}</span>
                  </button>
                ))}
              </div>
              {errs.role && <p className="mt-1 text-xs text-rose-400">{errs.role}</p>}
            </Field>
          </>
        )}
        <Field label="Mobile number" required>
          <TextInput type="tel" maxLength={10} placeholder="9876543210"
            value={mobile} onChange={(e) => setMobile(e.target.value.replace(/\D/g,""))} />
          {errs.mobile && <p className="mt-1 text-xs text-rose-400">{errs.mobile}</p>}
        </Field>
        <Field label="Password" required>
          <div className="relative">
            <TextInput type={showPass?"text":"password"}
              placeholder={mode==="register" ? "Create a password (min 4 chars)" : "Enter password"}
              value={pass} onChange={(e) => setPass(e.target.value)}
              onKeyDown={(e) => e.key==="Enter" && submit()} />
            <button type="button" onClick={() => setShowPass((v) => !v)}
              className="absolute right-3 top-1/2 -translate-y-1/2 t-sub hover:opacity-80 transition">
              {showPass ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
          {errs.pass && <p className="mt-1 text-xs text-rose-400">{errs.pass}</p>}
        </Field>
      </div>

      <PrimaryButton onClick={submit} loading={loading} disabled={loading} className="mt-4">
        {mode === "register" ? "Create account" : "Sign in"}
      </PrimaryButton>

      {mode === "login" && (
        <p className="mt-3 text-center text-xs t-muted">
          Don't have an account?{" "}
          <button className="text-emerald-500 underline" onClick={() => { setMode("register"); setErrs({}); }}>Register here</button>
        </p>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Crop card                                                                    */
/* ─────────────────────────────────────────────────────────────────────────── */
async function getBridges() {
  console.log("hiiiii");

  const json = {
    MACAddress: "Bridge-Web",
    SessionID: "487ba01b-d94c-4e22-84dc-4316e65854e2",
    ForumID: BRIDGE.forumID,
    UserDataLastCount: 0,
    UserDataFetchCount: 50,
    AdminDataLastCount: 0,
    AdminDataFetchCount: 50,
    ServerID: BRIDGE.serverID,
  };

  const res = await fetch(
    "https://fs.cosmitude.com/clientSyncForumBridgesPagination",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(json),
    }
  );

  const text = await res.text();

  console.log(JSON.parse(text));

  if (!text || !text.trim()) {
    throw new Error("Empty response");
  }

  try {
    return JSON.parse(text);
  } catch {
    return { raw: text };
  }

}

function parseBridgesToCrops(response) {
  const users = response?.ErrorMessage?.User;
  if (!Array.isArray(users)) return [];
  const farmerFlowID = BRIDGE.flows.farmer.id;
  const f = BRIDGE.fields.farmer;
  const dec = (v) => { try { return atob(v); } catch { return v; } };

  const bridges = users.map((u) => u?.Bridge).filter(Boolean);

  return bridges
    .filter((b) => b?.FlowID === farmerFlowID)
    .map((b) => {
      const flow = b[farmerFlowID] || {};
      const cropName = dec(flow[f.crop] || "") || "Unknown";
      return {
        id:              b.BridgeID,
        name:            cropName,
        emoji:           cropMeta(cropName).emoji,
        qty:             Number(dec(flow[f.qty] || "0")) || 0,
        district:        dec(flow[f.district] || ""),
        village:         dec(flow[f.village]  || ""),
        daysUntilHarvest:Number(dec(flow[f.days]    || "0")) || 0,
        notes:           dec(flow[f.notes]    || ""),
        status:          "pending",
      };
    });
}

function CropCard({ entry, onSell, onStore, onAdvisory }) {
  const upcoming = entry.daysUntilHarvest > 0;

  if (upcoming) return (
    <div className="rounded-2xl border t-border t-card p-4 flex items-center gap-3">
      <div className="flex h-11 w-11 items-center justify-center rounded-xl t-chip text-xl">{entry.emoji}</div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium t-text">{entry.name} · {entry.qty} MT</div>
        <div className="text-xs t-sub truncate">{entry.village ? entry.village + " · " : ""}{entry.district}</div>
      </div>
      <span className="inline-flex items-center gap-1 rounded-full t-chip px-2.5 py-1 text-xs t-sub">
        <Clock className="h-3 w-3" /> {entry.daysUntilHarvest}d
      </span>
    </div>
  );

  if (entry.status === "sold") return (
    <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-4 flex items-center gap-3">
      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/10 text-xl">{entry.emoji}</div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium t-text">{entry.name} · {entry.qty} MT</div>
        <div className="text-xs text-emerald-500 truncate">Sold to {entry.deal?.buyer} · {fmtINR(entry.deal?.total)}</div>
      </div>
      <CheckCircle2 className="h-5 w-5 text-emerald-500 flex-shrink-0" />
    </div>
  );

  if (entry.status === "stored") return (
    <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4 flex items-center gap-3">
      <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-amber-500/10 text-xl">{entry.emoji}</div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-medium t-text">{entry.name} · {entry.qty} MT</div>
        <div className="text-xs text-amber-500 truncate">In storage at {entry.deal?.facility} · {entry.deal?.days}d</div>
      </div>
      <PackageCheck className="h-5 w-5 text-amber-500 flex-shrink-0" />
    </div>
  );

  const advisory = useMemo(() => buildAdvisory(entry), [entry.id]);
  return (
    <div className="rounded-2xl border t-border t-card p-4">
      <div className="flex items-start gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl t-chip text-xl">{entry.emoji}</div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <div className="text-sm font-medium t-text">{entry.name} · {entry.qty} MT</div>
            <VerdictBadge verdict={advisory.verdict} />
          </div>
          <div className="text-xs t-sub">{entry.village ? entry.village + " · " : ""}{entry.district}</div>
        </div>
      </div>
      <div className="mt-3 flex items-center gap-3">
        <Sparkline trend={advisory.trend} verdict={advisory.verdict} />
        <div className="flex-1">
          <div className="flex items-baseline gap-1.5 flex-wrap">
            <span className="text-lg font-semibold t-text">{fmtINR(advisory.price)}</span>
            <span className="text-xs t-sub">/quintal</span>
            <span className={`ml-auto inline-flex items-center gap-0.5 text-xs font-medium ${advisory.changePct >= 0 ? "text-emerald-500" : "text-rose-500"}`}>
              {advisory.changePct >= 0 ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}
              {Math.abs(advisory.changePct).toFixed(1)}%
            </span>
          </div>
        </div>
      </div>
      <div className="mt-3 flex gap-2">
        <button onClick={() => onAdvisory(entry,advisory)}
          className={`flex-1 rounded-lg border border-amber-500/40 text-amber-500 font-semibold py-2 text-sm transition hover:bg-amber-500/10 active:scale-[0.98] flex items-center justify-center gap-1.5 ${advisory.reason}`}>
          <Sprout className="h-3.5 w-3.5" /> Advisory
        </button>
        <button onClick={() => onSell(entry, advisory)}
          className={`flex-1 rounded-lg bg-emerald-500 text-white font-semibold py-2 text-sm transition hover:bg-emerald-400 active:scale-[0.98] flex items-center justify-center gap-1.5 ${advisory.verdict==="sell" ? "ring-2 ring-emerald-400/60" : ""}`}>
          <ShoppingCart className="h-3.5 w-3.5" /> Sell now
        </button>
        <button onClick={() => onStore(entry, advisory)}
          className={`flex-1 rounded-lg border border-amber-500/40 text-amber-500 font-semibold py-2 text-sm transition hover:bg-amber-500/10 active:scale-[0.98] flex items-center justify-center gap-1.5 ${advisory.verdict==="store" ? "ring-2 ring-amber-400/60" : ""}`}>
          <Warehouse className="h-3.5 w-3.5" /> Store
        </button>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Role-specific home panels                                                    */
/* ─────────────────────────────────────────────────────────────────────────── */

function StatChip({ icon:Icon, value, label, color }) {
  return (
    <div className="flex-1 rounded-xl border t-border t-card p-3 text-center">
      <Icon className={`mx-auto h-4 w-4 mb-1 ${color}`} />
      <div className="text-base font-bold t-text">{value}</div>
      <div className="text-[10px] t-sub">{label}</div>
    </div>
  );
}

/* Farmer panel */
function FarmerPanel({ user, crops, onAddCrop, onSell, onStore, onAdvisory}) {
  const ready      = crops.filter((c) => c.daysUntilHarvest <= 0);
  console.log("ready",ready)
  const upcoming   = crops.filter((c) => c.daysUntilHarvest > 0);
  const actionable = ready.filter((c) => c.status==="pending").length;
  const stored     = crops.filter((c) => c.status==="stored").length;
  const sold       = crops.filter((c) => c.status==="sold").length;

  return (
    <div>
      <div className="flex gap-2 mb-5">
        <StatChip icon={Sprout}       value={actionable} label="Ready to act" color="text-emerald-500" />
        <StatChip icon={Warehouse}    value={stored}     label="In storage"   color="text-amber-500"   />
        <StatChip icon={ShoppingCart} value={sold}       label="Sold"         color="text-sky-500"     />
      </div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] font-medium uppercase tracking-wide t-sub">My crops</span>
        <button onClick={onAddCrop} className="flex items-center gap-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-1.5 text-xs font-medium text-emerald-500 hover:bg-emerald-500/20 transition">
          <Plus className="h-3.5 w-3.5" /> Add crop
        </button>
      </div>
      {crops.length===0 ? (
        <button onClick={onAddCrop} className="w-full rounded-2xl border border-dashed border-zinc-300 dark:border-zinc-700 hover:border-emerald-500/50 p-8 text-center transition group">
          <Sprout className="mx-auto h-8 w-8 mb-3 t-muted group-hover:text-emerald-500/60 transition" />
          <p className="text-sm font-medium t-sub">Add your first crop</p>
          <p className="text-xs t-muted mt-1">Get price advisory, match with buyers &amp; cold storage</p>
        </button>
      ) : (
        <div className="space-y-3">
          {ready.map((c) => <CropCard key={c.id} entry={c} onSell={onSell} onStore={onStore} onAdvisory={onAdvisory}/>)}
          {upcoming.length > 0 && (
            <>
              <div className="text-[11px] font-medium uppercase tracking-wide t-sub pt-2">Upcoming harvests</div>
              {upcoming.map((c) => <CropCard key={c.id} entry={c} onSell={onSell} onStore={onStore} onAdvisory={onAdvisory}/>)}
            </>
          )}
        </div>
      )}
    </div>
  );
}

/* Storage panel */
function StoragePanel({ user, bizData, onRegister }) {
  const [page, setPage] = useState(null);

  const myListings = Array.isArray(bizData.storage)
    ? bizData.storage
    : bizData.storage
    ? [bizData.storage]
    : [];

  async function updateBookingStatus(id, status) {
    const bookings = bizData.storageBookings || [];

    const updatedBookings = bookings.map((b) =>
      b.id === id
        ? { ...b, status }
        : b
    );
    const updatedBizData = {
      ...bizData,
      storageBookings: updatedBookings
    };

    try {

      await saveUserData(
        user.mobile,
        "bizdata",
        updatedBizData
      );

      alert(
        status === "accepted"
          ? "Booking accepted"
          : "Booking rejected"
      );

      window.location.reload();

    } catch (err) {

      console.error(err);

      alert("Failed to update booking");

    }
  }

  return (
    <div>
      <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4 mb-4 flex items-start gap-3">
        <Warehouse className="h-5 w-5 text-amber-500 flex-shrink-0 mt-0.5" />
        <div>
          <div className="text-sm font-semibold t-text mb-0.5">
            Cold Storage Operator Dashboard
          </div>
          <div className="text-xs t-sub">
            Manage your facility listings and incoming bookings from farmers.
          </div>
        </div>
      </div>

      {myListings.length > 0 ? (
        <>
          <button
            onClick={onRegister}
            className="mb-3 w-full rounded-xl bg-amber-500 text-white py-2 text-sm font-medium hover:bg-amber-400 transition"
          >
            + Add Another Storage
          </button>

          {myListings.map((s, i) => (
            <div
              key={i}
              className="rounded-2xl border t-border t-card p-4 mb-3"
            >
              <div className="flex justify-between items-center">
                <div className="text-sm font-semibold t-text">
                  {s.facility}
                </div>

                <span className="text-[10px] bg-amber-500/10 text-amber-500 px-2 py-1 rounded-full">
                  Facility {i + 1}
                </span>
              </div>

              <div className="text-xs t-sub mt-1">
                {s.district} · {s.cap} MT capacity · ₹{s.rate}/MT/day
              </div>
            </div>
          ))}
        </>
      ) : (
        <div className="rounded-2xl border border-dashed border-zinc-300 dark:border-zinc-700 p-6 text-center mb-4">
          <Warehouse className="mx-auto h-8 w-8 mb-3 t-muted" />
          <p className="text-sm font-medium t-sub">
            No facility listed yet
          </p>
          <p className="text-xs t-muted mt-1 mb-3">
            List your cold storage to connect with nearby farmers
          </p>

          <button
            onClick={onRegister}
            className="inline-flex items-center gap-1.5 rounded-lg bg-amber-500 text-white px-4 py-2 text-sm font-medium hover:bg-amber-400 transition"
          >
            <Plus className="h-3.5 w-3.5" />
            List my facility
          </button>
        </div>
      )}

      <div className="rounded-2xl border t-border t-card divide-y t-divide">
        {[
          {
            page: "bookings",
            label: "Manage bookings",
            Icon: PackageCheck,
            sub: "View incoming storage requests",
          },
          {
            page: "availability",
            label: "Update availability",
            Icon: RefreshCw,
            sub: "Change capacity or rates",
          },
          {
            page: "earnings",
            label: "View earnings",
            Icon: IndianRupee,
            sub: "Storage revenue summary",
          },
        ].map(({ page: pageName, label, Icon, sub }) => (
          <button
            key={label}
            onClick={() => {
              console.log("CLICKED =", pageName);
              setPage(pageName);
            }}
            className="w-full flex items-center gap-3 p-3.5 hover:bg-white/5 transition"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-amber-500/10">
              <Icon className="h-4 w-4 text-amber-500" />
            </div>

            <div className="flex-1 text-left">
              <div className="text-sm font-medium t-text">
                {label}
              </div>

              <div className="text-xs t-sub">
                {sub}
              </div>
            </div>

            <ChevronRight className="h-4 w-4 t-muted" />
          </button>
        ))}
      </div>

      {page === "bookings" && (
  <div className="rounded-xl border t-border t-card p-4 mt-4">
    <h3 className="font-semibold mb-3">
      Manage Bookings
    </h3>

    {(bizData.storageBookings || []).length === 0 ? (
      <p className="text-sm t-sub">
        No bookings yet.
      </p>
    ) : (
      bizData.storageBookings.map((b) => (
        <div
          key={b.id}
          className="border rounded-xl p-3 mb-3"
        >
          <div className="font-medium">
            {b.farmerName}
          </div>

          <div className="text-sm">
            {b.crop}
          </div>

          <div className="text-sm">
            {b.qty} MT
          </div>

          <div className="flex gap-2 mt-2">
            <button onClick={() =>
              updateBookingStatus(b.id,"accepted")}>
              Accept
            </button>

            <button onClick={() => updateBookingStatus(b.id, "rejected")}>
              Reject
            </button>
          </div>
        </div>
      ))
    )}
  </div>
)}

      {page === "availability" && (
        <div className="rounded-xl border t-border t-card p-4 mt-4">
          <h3 className="font-semibold mb-2">
            Update Availability
          </h3>

          <p className="text-sm t-sub">
            Capacity and rate update screen.
          </p>
        </div>
      )}

      {page === "earnings" && (
        <div className="rounded-xl border t-border t-card p-4 mt-4">
          <h3 className="font-semibold mb-2">
            Earnings
          </h3>

          <p className="text-sm t-sub">
            Total revenue: ₹0
          </p>
        </div>
      )}
    </div>
  );
}

/* Transport panel */
function TransportPanel({ user, bizData, onRegister }) {
  const [page, setPage] = useState(null);

  const myFleet = Array.isArray(bizData.transport)
    ? bizData.transport
    : bizData.transport
    ? [bizData.transport]
    : [];

  return (
    <div>
      <div className="rounded-2xl border border-sky-500/20 bg-sky-500/5 p-4 mb-4 flex items-start gap-3">
        <Truck className="h-5 w-5 text-sky-500 flex-shrink-0 mt-0.5" />
        <div>
          <div className="text-sm font-semibold t-text mb-0.5">
            Transporter Dashboard
          </div>
          <div className="text-xs t-sub">
            Register your vehicle to get matched with farmers needing transport.
          </div>
        </div>
      </div>

      {myFleet.length > 0 ? (
        <>
          <button
            onClick={onRegister}
            className="mb-3 w-full rounded-xl bg-sky-500 text-white py-2 text-sm font-medium hover:bg-sky-400 transition"
          >
            + Add Another Vehicle
          </button>

          {myFleet.map((v, i) => (
            <div
              key={i}
              className="rounded-2xl border t-border t-card p-4 mb-3"
            >
              <div className="flex justify-between items-center">
                <div className="text-sm font-semibold t-text">
                  {v.name}
                </div>

                <span className="text-[10px] bg-sky-500/10 text-sky-500 px-2 py-1 rounded-full">
                  Vehicle {i + 1}
                </span>
              </div>

              <div className="text-xs t-sub mt-1">
                {v.vehicle} · {v.district} · ₹{v.rate}/MT/km
              </div>
            </div>
          ))}
        </>
      ) : (
        <div className="rounded-2xl border border-dashed border-zinc-300 dark:border-zinc-700 p-6 text-center mb-4">
          <Truck className="mx-auto h-8 w-8 mb-3 t-muted" />

          <p className="text-sm font-medium t-sub">
            No vehicle registered yet
          </p>

          <p className="text-xs t-muted mt-1 mb-3">
            Register to start getting transport requests from farmers
          </p>

          <button
            onClick={onRegister}
            className="inline-flex items-center gap-1.5 rounded-lg bg-sky-500 text-white px-4 py-2 text-sm font-medium hover:bg-sky-400 transition"
          >
            <Plus className="h-3.5 w-3.5" />
            Register vehicle
          </button>
        </div>
      )}

      <div className="rounded-2xl border t-border t-card divide-y t-divide">
        {[
          {
            page: "active",
            label: "Active trips",
            Icon: Truck,
            sub: "Jobs in progress",
          },
          {
            page: "requests",
            label: "New requests",
            Icon: Bell,
            sub: "Farmers looking for transport",
          },
          {
            page: "history",
            label: "Trip history",
            Icon: HistoryIcon,
            sub: "Past completed runs",
          },
        ].map(({ page: pageName, label, Icon, sub }) => (
          <button
            key={label}
            onClick={() => {
              console.log("CLICKED =", pageName);
              setPage(pageName);
            }}
            className="w-full flex items-center gap-3 p-3.5 hover:bg-white/5 transition"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-500/10">
              <Icon className="h-4 w-4 text-sky-500" />
            </div>

            <div className="flex-1 text-left">
              <div className="text-sm font-medium t-text">
                {label}
              </div>

              <div className="text-xs t-sub">
                {sub}
              </div>
            </div>

            <ChevronRight className="h-4 w-4 t-muted" />
          </button>
        ))}
      </div>

      {page === "active" && (
        <div className="rounded-xl border t-border t-card p-4 mt-4">
          <h3 className="font-semibold mb-2">
            Active Trips
          </h3>

          <p className="text-sm t-sub">
            No active trips.
          </p>
        </div>
      )}

      {page === "requests" && (
        <div className="rounded-xl border t-border t-card p-4 mt-4">
          <h3 className="font-semibold mb-2">
            New Requests
          </h3>

          <p className="text-sm t-sub">
            No transport requests yet.
          </p>
        </div>
      )}

      {page === "history" && (
        <div className="rounded-xl border t-border t-card p-4 mt-4">
          <h3 className="font-semibold mb-2">
            Trip History
          </h3>

          <p className="text-sm t-sub">
            No completed trips yet.
          </p>
        </div>
      )}
    </div>
  );
}

/* Trader panel */
function TraderPanel({ user, bizData, onRegister }) {
  const [page, setPage] = useState(null);

  const myProfiles = Array.isArray(bizData.trader)
    ? bizData.trader
    : bizData.trader
    ? [bizData.trader]
    : [];

  console.log("TRADER PAGE =", page);

  return (
    <div>
      <div className="rounded-2xl border border-violet-500/20 bg-violet-500/5 p-4 mb-4 flex items-start gap-3">
        <Building2 className="h-5 w-5 text-violet-500 flex-shrink-0 mt-0.5" />

        <div>
          <div className="text-sm font-semibold t-text mb-0.5">
            Trader / Buyer Dashboard
          </div>

          <div className="text-xs t-sub">
            Browse available produce and connect directly with farmers.
          </div>
        </div>
      </div>

      {myProfiles.length > 0 ? (
        <>
          <button
            onClick={onRegister}
            className="mb-3 w-full rounded-xl bg-violet-500 text-white py-2 text-sm font-medium hover:bg-violet-400 transition"
          >
            + Add Another Buyer Profile
          </button>

          {myProfiles.map((p, i) => (
            <div
              key={i}
              className="rounded-2xl border t-border t-card p-4 mb-3"
            >
              <div className="flex justify-between items-center">
                <div className="text-sm font-semibold t-text">
                  {p.company}
                </div>

                <span className="text-[10px] bg-violet-500/10 text-violet-500 px-2 py-1 rounded-full">
                  Profile {i + 1}
                </span>
              </div>

              <div className="text-xs t-sub mt-1">
                {p.district} · Trades: {p.crops}
              </div>
            </div>
          ))}
        </>
      ) : (
        <div className="rounded-2xl border border-dashed border-zinc-300 dark:border-zinc-700 p-6 text-center mb-4">
          <Building2 className="mx-auto h-8 w-8 mb-3 t-muted" />

          <p className="text-sm font-medium t-sub">
            No buyer profile yet
          </p>

          <p className="text-xs t-muted mt-1 mb-3">
            Register to browse farmers and lock in deals
          </p>

          <button
            onClick={onRegister}
            className="inline-flex items-center gap-1.5 rounded-lg bg-violet-500 text-white px-4 py-2 text-sm font-medium hover:bg-violet-400 transition"
          >
            <Plus className="h-3.5 w-3.5" />
            Register as Buyer
          </button>
        </div>
      )}

      <div className="rounded-2xl border t-border t-card divide-y t-divide">
        {[
          {
            page: "browse",
            label: "Browse Listings",
            Icon: Wheat,
            sub: "Crops available near you",
          },
          {
            page: "bids",
            label: "My Bids",
            Icon: ShoppingCart,
            sub: "Track your active offers",
          },
          {
            page: "rates",
            label: "Market Rates",
            Icon: TrendingUp,
            sub: "Live mandi prices",
          },
        ].map(({ page: pageName, label, Icon, sub }) => (
          <button
            key={label}
            onClick={() => {
              console.log("CLICKED =", pageName);
              setPage(pageName);
            }}
            className="w-full flex items-center gap-3 p-3.5 hover:bg-white/5 transition"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-500/10">
              <Icon className="h-4 w-4 text-violet-500" />
            </div>

            <div className="flex-1 text-left">
              <div className="text-sm font-medium t-text">
                {label}
              </div>

              <div className="text-xs t-sub">
                {sub}
              </div>
            </div>

            <ChevronRight className="h-4 w-4 t-muted" />
          </button>
        ))}
      </div>

      {page === "browse" && (
        <div className="rounded-xl border t-border t-card p-4 mt-4">
          <h3 className="font-semibold mb-2">
            Browse Listings
          </h3>

          <p className="text-sm t-sub">
            No farmer listings available yet.
          </p>
        </div>
      )}

      {page === "bids" && (
        <div className="rounded-xl border t-border t-card p-4 mt-4">
          <h3 className="font-semibold mb-2">
            My Bids
          </h3>

          <p className="text-sm t-sub">
            No active bids.
          </p>
        </div>
      )}

      {page === "rates" && (
        <div className="rounded-xl border t-border t-card p-4 mt-4">
          <h3 className="font-semibold mb-2">
            Market Rates
          </h3>

          <p className="text-sm t-sub">
            Market price dashboard coming soon.
          </p>
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Advisory text parser + display                                               */
/* ─────────────────────────────────────────────────────────────────────────── */

function parseAdvisoryText(text) {
  const lines = text.split("\n");
  const get = (prefix) => {
    const l = lines.find((l) => l.trimStart().startsWith(prefix));
    return l ? l.slice(l.indexOf(prefix) + prefix.length).trim() : null;
  };

  const findValue = (key) => {
    const line = lines.find((l) =>
      l.replace(/\s/g, "").toLowerCase()
        .startsWith(key.replace(/\s/g, "").toLowerCase())
    );

    if (!line) return null;

    const idx = line.indexOf(":");
    return idx >= 0 ? line.slice(idx + 1).trim() : null;
  };

  // Farmer info block (top)
  const farmerStatus = lines[0]?.trim() || "";
  const id       = get("ID:");
  const nameLine = get("Name:");
  const location = get("Location:");
  const cropLine = get("Crop:");
  const harvest  = get("Harvest date:");
  const saveId   = lines.find((l) => l.startsWith("Save your Farmer ID:"))?.replace("Save your Farmer ID:", "").trim();

  // Storage section

  const storageMatchLine = lines.find((l) => /COLD STORAGE MATCH/.test(l));
  const storageFound     = !!storageMatchLine;
  const storageDistance  = storageMatchLine?.match(/\((.+?)\)/)?.[1] || "";
  const storageFacility  = findValue("  Facility :")?.replace(/^:?\s*/, "");
  const storageAddress   = findValue("  Address  :");
  const storageContact   = findValue("  Contact  :");
  const storageAvail     = findValue("  Available:");
  const storageRate      = findValue("  Rate     :");
  const storagePeriod    = findValue("  Period   :");

  // Transport section
  const transportMatchLine = lines.find((l) => /TRANSPORT MATCH/.test(l));
  const transportFound     = !!transportMatchLine;
  const transportDistance  = transportMatchLine?.match(/\((.+?)\)/)?.[1] || "";
  const transportName      = get("  Name     :");
  const transportPhone     = get("  Phone    :");
  const transportVehicle   = get("  Vehicle  :");
  const transportRate      = get("  Rate     :");

  // Market section
  const marketStart  = lines.findIndex((l) => /Market & Trader Demand/.test(l));
  const storeStart   = lines.findIndex((l) => /If You Choose STORE/.test(l));
  const marketLines  = marketStart >= 0 ? lines.slice(marketStart + 1, storeStart >= 0 ? storeStart : undefined) : [];
  const mandiLine    = marketLines.find((l) => /Mandi/.test(l) && /price now/.test(l));
  const forecastLine = marketLines.find((l) => /Forecast in/.test(l));
  const tradersLine  = marketLines.find((l) => /Traders ready to buy/.test(l));
  const recLines     = marketLines.filter((l) => l.trim() && !/^Mandi|^Forecast|^Traders/.test(l.trim()) && !/^---/.test(l.trim()));

  // Store advisory section
  const storeLines        = storeStart >= 0 ? lines.slice(storeStart + 1) : [];
  const storageOnHarvest  = storeLines.find((l) => /Storage on harvest/.test(l));
  const transportOnHarvest= storeLines.find((l) => /Transport on harvest/.test(l));
  const cheapestLine      = storeLines.find((l) => /Cheapest storage/.test(l));
  const costLine          = storeLines.find((l) => /7d=/.test(l));

  return {
    farmerStatus, id, nameLine, location, cropLine, harvest, saveId,
    storage: storageFound ? { distance: storageDistance, facility: storageFacility, address: storageAddress, contact: storageContact, avail: storageAvail, rate: storageRate, period: storagePeriod } : null,
    transport: transportFound ? { distance: transportDistance, name: transportName, phone: transportPhone, vehicle: transportVehicle, rate: transportRate } : null,
    market: { mandi: mandiLine, forecast: forecastLine, traders: tradersLine, recommendation: recLines.filter(Boolean).join("\n") },
    storeAdvisory: { storageOnHarvest, transportOnHarvest, cheapest: cheapestLine, costs: costLine },
  };
}

function InfoRow({ label, value }) {
  if (!value) return null;
  return (
    <div className="flex justify-between gap-3 py-1.5 border-b t-border last:border-0">
      <span className="text-xs t-sub shrink-0">{label}</span>
      <span className="text-xs font-medium t-text text-right">{value}</span>
    </div>
  );
}

function AdvisoryDisplay({ text }) {
  const d = parseAdvisoryText(text);
  const isSuccess = d.farmerStatus.startsWith("✅");

  return (
    <div className="space-y-4">
      {/* Status header */}
      <div className={`rounded-xl border p-3 ${isSuccess ? "border-emerald-500/30 bg-emerald-500/5" : "border-rose-500/30 bg-rose-500/5"}`}>
        <p className={`text-sm font-semibold ${isSuccess ? "text-emerald-500" : "text-rose-500"}`}>{d.farmerStatus}</p>
        {d.id       && <p className="text-xs t-sub mt-1">ID: <span className="font-mono t-text">{d.id}</span></p>}
        {d.harvest  && <p className="text-xs t-sub mt-0.5">Harvest: {d.harvest}</p>}
      </div>

      {/* Farmer details */}
      {(d.nameLine || d.location || d.cropLine) && (
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide t-sub mb-2">Farmer Details</p>
          <div className="rounded-xl border t-border t-card p-3">
            {d.nameLine  && <InfoRow label="Name / Phone" value={d.nameLine} />}
            {d.location  && <InfoRow label="Location"     value={d.location} />}
            {d.cropLine  && <InfoRow label="Crop"         value={d.cropLine} />}
          </div>
        </div>
      )}

      {/* Cold storage */}
      {d.storage ? (
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide t-sub mb-2">
            Cold Storage Match {d.storage.distance && <span className="normal-case">({d.storage.distance})</span>}
          </p>
          <div className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-3">
            {d.storage.facility && <p className="text-sm font-semibold t-text mb-2">{d.storage.facility}</p>}
            <div>
              {d.storage.rate    && <InfoRow label="Rate"      value={d.storage.rate} />}
              {d.storage.avail   && <InfoRow label="Available" value={d.storage.avail} />}
              {d.storage.period  && <InfoRow label="Period"    value={d.storage.period} />}
              {d.storage.address && <InfoRow label="Address"   value={d.storage.address} />}
              {d.storage.contact && <InfoRow label="Contact"   value={d.storage.contact} />}
            </div>
          </div>
        </div>
      ) : (
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide t-sub mb-2">Cold Storage</p>
          <div className="rounded-xl border t-border t-card p-3 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
            <span className="text-xs t-sub">No cold storage found nearby for this crop and dates.</span>
          </div>
        </div>
      )}

      {/* Transport */}
      {d.transport ? (
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide t-sub mb-2">
            Transport Match {d.transport.distance && <span className="normal-case">({d.transport.distance})</span>}
          </p>
          <div className="rounded-xl border border-sky-500/30 bg-sky-500/5 p-3">
            {d.transport.name    && <p className="text-sm font-semibold t-text mb-2">{d.transport.name}</p>}
            {d.transport.vehicle && <InfoRow label="Vehicle" value={d.transport.vehicle} />}
            {d.transport.rate    && <InfoRow label="Rate"    value={d.transport.rate} />}
            {d.transport.phone   && <InfoRow label="Phone"   value={d.transport.phone} />}
          </div>
        </div>
      ) : (
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide t-sub mb-2">Transport</p>
          <div className="rounded-xl border t-border t-card p-3 flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
            <span className="text-xs t-sub">No transporter found for this area and dates.</span>
          </div>
        </div>
      )}

      {/* Market & Trader Demand */}
      {(d.market.mandi || d.market.traders || d.market.recommendation) && (
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide t-sub mb-2">Market & Trader Demand</p>
          <div className="rounded-xl border t-border t-card p-3 space-y-1.5">
            {d.market.mandi    && <p className="text-xs t-text">{d.market.mandi.trim()}</p>}
            {d.market.forecast && <p className="text-xs t-sub">{d.market.forecast.trim()}</p>}
            {d.market.traders  && <p className="text-xs t-sub">{d.market.traders.trim()}</p>}
            {d.market.recommendation && (
              <p className="text-xs font-medium text-emerald-500 pt-1 border-t t-border mt-1">{d.market.recommendation}</p>
            )}
          </div>
        </div>
      )}

      {/* If You Choose Store */}
      {(d.storeAdvisory.storageOnHarvest || d.storeAdvisory.transportOnHarvest) && (
        <div>
          <p className="text-[11px] font-medium uppercase tracking-wide t-sub mb-2">If You Choose Store</p>
          <div className="rounded-xl border t-border t-card p-3 space-y-1.5">
            {d.storeAdvisory.storageOnHarvest   && <p className="text-xs t-text">{d.storeAdvisory.storageOnHarvest.trim()}</p>}
            {d.storeAdvisory.transportOnHarvest && <p className="text-xs t-text">{d.storeAdvisory.transportOnHarvest.trim()}</p>}
            {d.storeAdvisory.cheapest && <p className="text-xs t-sub">{d.storeAdvisory.cheapest.trim()}</p>}
            {d.storeAdvisory.costs    && <p className="text-xs t-sub">{d.storeAdvisory.costs.trim()}</p>}
          </div>
        </div>
      )}

      {/* Save ID */}
      {d.saveId && (
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-3">
          <p className="text-xs t-sub">Save your Farmer ID</p>
          <p className="text-sm font-mono font-semibold text-emerald-500 mt-0.5">{d.saveId}</p>
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Home tab — role-aware, multi-role tabs                                       */
/* ─────────────────────────────────────────────────────────────────────────── */

function HomeTab({ user, crops, bizData, onAddCrop, onSell, onStore, onRegisterRole, onAdvisory }) {

  // Holds the cold-storage match (plus the Farmer ID) that came back from the
  // last advisory the farmer looked at. This — and only this — is what gets
  // offered when they tap "Store" on a crop.
  const [advisoryStorage, setAdvisoryStorage] = useState(null);
  const hour     = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const activeRoles = user.activeRoles || [user.role || "farmer"];

  // which role panel is shown
  const [activePanel, setActivePanel] = useState(activeRoles[0]);

  // keep activePanel valid if activeRoles changes
  useEffect(() => {
    if (!activeRoles.includes(activePanel)) setActivePanel(activeRoles[0]);
  }, [activeRoles.join(",")]);

  const [bridgeCrops, setBridgeCrops] = useState([]);
  const [rawBridges,    setRawBridges]    = useState([]);
  async function refreshBridges() {
    try {
      const data = await getBridges();
      console.log("USER BRIDGES =", data.ErrorMessage?.User);
      console.log("ADMIN BRIDGES =", data.ErrorMessage?.Admin);

      const msg = data?.ErrorMessage;

      const users = Array.isArray(msg?.User)
        ? msg.User.map((u) => u?.Bridge).filter(Boolean)
        : [];

      const admins = Array.isArray(msg?.Admin)
        ? msg.Admin.map((a) => a?.Bridge).filter(Boolean)
        : [];

      setRawBridges([...users, ...admins]);
      setBridgeCrops(parseBridgesToCrops(data));

    } catch (err) {
      console.error(err);
    }
  }
  const [advisoryBridge, setAdvisoryBridge] = useState(null);
  useEffect(() => {
    refreshBridges();
  }, []);

  function handleGetBridge(bridgeId) {
    const bridge = rawBridges.find((b) => b.BridgeID === bridgeId);
    console.log("bridge data:", bridge);
  }
  async function handleFarmerAdvisory(entry) {

    console.log("ENTRY =", entry);

    console.log("ENTRY BRIDGE ID =", entry.bridgeId);
    console.log("RAW BRIDGES =", rawBridges);

    rawBridges.forEach((b) => {
      console.log("REPLY ID =", b.ReplyBridgeID);
    });

    let replyBridge = rawBridges.find(
      (b) =>
        b.ReplyBridgeID === entry.bridgeId ||
        b.ReplyBridgeID === entry.id
    );
    if (!replyBridge) {

    console.log("Refreshing bridges...");

    const data = await getBridges();
    
    console.log("ALL BRIDGES =", data);
    const msg = data?.ErrorMessage;

    const users = Array.isArray(msg?.User)
      ? msg.User.map((u) => u?.Bridge).filter(Boolean)
      : [];

    const admins = Array.isArray(msg?.Admin)
      ? msg.Admin.map((a) => a?.Bridge).filter(Boolean)
      : [];

    const freshBridges = [...users, ...admins];
    console.log("ENTRY BRIDGE =", entry.bridgeId);

  freshBridges.forEach((b) => {
    console.log("BRIDGE OBJECT =", b);
  });

    const freshReply = freshBridges.find(
      (b) =>
        b.ReplyBridgeID === entry.bridgeId ||
        b.ReplyBridgeID === entry.id
    );

    if (!freshReply) {
      console.log(
        "no reply bridge found for",
        entry.bridgeId,
        entry.id
      );  
      return;
    }
    replyBridge = freshReply;
  }
    const flowData = replyBridge[replyBridge.FlowID] || {};

    const decodeB64 = (v) => {
      try {
        return decodeURIComponent(escape(atob(v)));
      } catch {
        try {
          return atob(v);
        } catch {
          return v;
        }
      }
    };
    const decoded = Object.fromEntries(
      Object.entries(flowData).map(([key, value]) => [
        key,
        typeof value === "string" ? decodeB64(value) : value
      ])
    );
    const advisoryText = Object.values(decoded)[0] || "";
    const parsed = parseAdvisoryText(advisoryText);
    // Store the advisory's suggested cold storage, plus the Farmer ID — the
    // booking flow needs both to tell the backend which farmer/storage to block.
    setAdvisoryStorage(
      parsed.storage
        ? { ...parsed.storage, farmerId: parsed.id || parsed.saveId || "" }
        : null
    );
    setAdvisoryBridge({ bridge: replyBridge, decoded });
  }

  const roleMeta = {
    farmer:    { label:"Farmer",   color:"text-emerald-500", border:"border-emerald-500", activeBg:"bg-emerald-500/10" },
    storage:   { label:"Storage",  color:"text-amber-500",   border:"border-amber-500",   activeBg:"bg-amber-500/10"   },
    transport: { label:"Transport",color:"text-sky-500",     border:"border-sky-500",     activeBg:"bg-sky-500/10"     },
    trader:    { label:"Trader",   color:"text-violet-500",  border:"border-violet-500",  activeBg:"bg-violet-500/10"  },
  };

  return (
    <div className="px-4 pt-4 pb-6">
      <div className="mb-4">
        <h2 className="text-lg font-bold t-text">{greeting}, {(user?.name || "Farmer").split(" ")[0]} 👋</h2>
        <p className="text-sm t-sub">Here's your KrishiSetu overview.</p>
      </div>

      {/* Role tabs — only shown when user has multiple roles */}
      {activeRoles.length > 1 && (
        <div className="flex gap-1.5 mb-5 overflow-x-auto scrollbar-hide pb-1">
          {activeRoles.map((r) => {
            const m = roleMeta[r];
            const active = activePanel === r;
            return (
              <button key={r} onClick={() => setActivePanel(r)}
                className={`flex-shrink-0 rounded-xl border px-3 py-1.5 text-xs font-medium transition
                  ${active ? `${m.border} ${m.activeBg} ${m.color}` : "t-border t-sub t-chip"}`}>
                {m.label}
              </button>
            );
          })}
        </div>
      )}

      {/* Render the matching panel */}
      {activePanel === "farmer" && (
        <FarmerPanel user={user} crops={crops} onAddCrop={onAddCrop} onSell={onSell}
          onStore={(entry, advisory) => onStore(entry, advisory, advisoryStorage)}
          onAdvisory={handleFarmerAdvisory} onGetBridge={handleGetBridge} />
      )}
      {activePanel === "storage" && (
        <StoragePanel user={user} bizData={bizData} onRegister={() => onRegisterRole("storage")} />
      )}
      {activePanel === "transport" && (
        <TransportPanel user={user} bizData={bizData} onRegister={() => onRegisterRole("transport")} />
      )}
      {activePanel === "trader" && (
        <TraderPanel user={user} bizData={bizData} onRegister={() => onRegisterRole("trader")} />
      )}

      {advisoryBridge && (
        <Sheet title="Crop Advisory" onClose={() => setAdvisoryBridge(null)}>
          <AdvisoryDisplay text={Object.values(advisoryBridge.decoded)[0] || ""} />
        </Sheet>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Sell sheet                                                                   */
/* ─────────────────────────────────────────────────────────────────────────── */

function SellSheet({ entry, advisory, user, onClose, onConfirm }) {
  const [buyers, setBuyers] = useState([]);
  useEffect(() => {
    async function loadBuyers() {
      const matches = await getBuyerMatches(
        entry,
        advisory.price,
        user?.mobile
      );

      setBuyers(matches);
    }

    loadBuyers();
  }, [entry.id, user?.mobile, advisory.price]);


    const [picked, setPicked] = useState(0);
    const [done,   setDone]   = useState(null);

  if (done) return (
    <Sheet title="Sale confirmed" onClose={onClose}>
      <div className="text-center py-4">
        <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/10 border border-emerald-500/30">
          <CheckCircle2 className="h-8 w-8 text-emerald-500" />
        </div>
        <div className="text-base font-semibold t-text mb-1">Deal locked in!</div>
        <div className="text-sm t-sub mb-4">{done.buyer} · {fmtINR(done.total)}</div>
        <div className="rounded-xl t-card border t-border p-3 text-left text-sm">
          {[["Deal ID",done.id],["Quantity",`${entry.qty} MT`],["Rate",`${fmtINR(done.price)}/quintal`],["Total",fmtINR(done.total)]].map(([k,v]) => (
            <div key={k} className="flex justify-between py-1.5 border-b t-border last:border-0">
              <span className="t-sub">{k}</span>
              <span className={`font-medium ${k==="Total" ? "text-emerald-500" : "t-text"}`}>{v}</span>
            </div>
          ))}
        </div>
        <PrimaryButton className="mt-4" onClick={onClose}>Done</PrimaryButton>
      </div>
    </Sheet>
  );

  // No registered buyers at all
  if (buyers.length === 0) return (
    <Sheet title={`Sell ${entry.name} · ${entry.qty} MT`} onClose={onClose}>
      <div className="text-center py-10">
        <Building2 className="mx-auto h-10 w-10 t-muted mb-3 opacity-40" />
        <p className="text-sm font-medium t-text mb-1">No buyers found</p>
        <p className="text-xs t-sub max-w-[220px] mx-auto leading-relaxed">
          No traders have registered on KrishiSetu yet who buy {entry.name}.
          Ask buyers in your area to sign up as a Trader.
        </p>
      </div>
      <GhostButton onClick={onClose}>Close</GhostButton>
    </Sheet>
  );

  return (
    <Sheet title={`Sell ${entry.name} · ${entry.qty} MT`} onClose={onClose}>
      <p className="text-xs t-sub mb-3">{buyers.length} registered buyer{buyers.length > 1 ? "s" : ""} found · ranked by offer price.</p>
      <div className="space-y-2">
        {buyers.map((b, i) => (
          <button key={i} onClick={() => setPicked(i)}
            className={`w-full rounded-xl border p-3 text-left transition ${picked===i ? "border-emerald-500 bg-emerald-500/5" : "t-border t-card"}`}>
            <div className="flex items-center justify-between">
              <div className="text-sm font-medium t-text">{b.company || b.ownerName}</div>
              {i===0 && <span className="text-[10px] font-medium text-emerald-500 bg-emerald-500/10 rounded-full px-2 py-0.5">Best price</span>}
            </div>
            <div className="mt-1 flex items-center gap-3 text-xs t-sub flex-wrap">
              <span className="flex items-center gap-1"><IndianRupee className="h-3 w-3" />{b.price}/quintal</span>
              {b.district && <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{b.district}</span>}
              {b.ownerPhone && <span className="flex items-center gap-1"><Phone className="h-3 w-3" />{b.ownerPhone}</span>}
            </div>
          </button>
        ))}
      </div>
      <div className="mt-4 rounded-xl t-card border t-border p-3 flex items-center justify-between">
        <div>
          <div className="text-xs t-sub">You'll receive</div>
          <div className="text-[11px] t-muted">{fmtINR(buyers[picked].price)}/quintal × {entry.qty} MT</div>
        </div>
        <div className="text-lg font-semibold text-emerald-500">{fmtINR(buyers[picked].price * entry.qty * 10)}</div>
      </div>
      <PrimaryButton className="mt-3" onClick={() => {
        const b = buyers[picked];
        const total  = b.price * entry.qty * 10;
        const dealId = "SL-" + Math.random().toString(36).slice(2,8).toUpperCase();
        const deal   = { id:dealId, buyer: b.company || b.ownerName, price:b.price, total };
        setDone(deal);
        onConfirm(deal);
      }}>Confirm sale</PrimaryButton>
    </Sheet>
  );
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Store sheet                                                                  */
/* ─────────────────────────────────────────────────────────────────────────── */

function StoreSheet({ entry, advisoryStorage, user, onClose, onConfirm }) {
  const [transports, setTransports] = useState([]);
  const [pickupDate, setPickupDate] = useState(
    new Date()
      .toISOString()
      .split("T")[0]
  );

  useEffect(() => {
    setTransports(getTransportMatches(entry, user?.mobile, pickupDate));
  }, [entry.id, user?.mobile, pickupDate]);

  const [pickedTransport, setPickedTransport] = useState(0);
  const [days,            setDays]            = useState(30);
  const [done,            setDone]            = useState(null);
  const [submitting,      setSubmitting]      = useState(false);

  // Only the storage facility surfaced by this crop's advisory is offered —
  // no local cross-user matching anymore.
  const facility     = advisoryStorage || null;
  const transporter  = transports[pickedTransport] || null;
  const cost         = facility ? parseRateValue(facility.rate) * entry.qty * days : 0;

  if (done) return (
    <Sheet title="Storage booked" onClose={onClose}>
      <div className="text-center py-4">
        <div className="mx-auto mb-3 flex h-16 w-16 items-center justify-center rounded-full bg-amber-500/10 border border-amber-500/30">
          <PackageCheck className="h-8 w-8 text-amber-500" />
        </div>
        <div className="text-base font-semibold t-text mb-1">Booking confirmed!</div>
        <div className="text-sm t-sub mb-4">{done.facility} · {done.days} days</div>
        <div className="rounded-xl t-card border t-border p-3 text-left text-sm">
          {[["Booking ID",done.id],["Quantity",`${entry.qty} MT`],["Duration",`${done.days} days`],["Est. cost",fmtINR(done.cost)]].map(([k,v]) => (
            <div key={k} className="flex justify-between py-1.5 border-b t-border last:border-0">
              <span className="t-sub">{k}</span>
              <span className={`font-medium ${k==="Est. cost" ? "text-amber-500" : "t-text"}`}>{v}</span>
            </div>
          ))}
        </div>
        <PrimaryButton className="mt-4 !bg-amber-500 hover:!bg-amber-400" onClick={onClose}>Done</PrimaryButton>
      </div>
    </Sheet>
  );

  // No advisory-suggested storage available for this crop yet
  if (!facility) return (
    <Sheet title={`Store ${entry.name} · ${entry.qty} MT`} onClose={onClose}>
      <div className="text-center py-10">
        <Warehouse className="mx-auto h-10 w-10 t-muted mb-3 opacity-40" />
        <p className="text-sm font-medium t-text mb-1">No advisory storage match</p>
        <p className="text-xs t-sub max-w-[220px] mx-auto leading-relaxed">
          Tap "Advisory" on this crop first to get a cold storage match from KrishiSetu — that's what you'll be able to book here.
        </p>
      </div>
      <GhostButton onClick={onClose}>Close</GhostButton>
    </Sheet>
  );

  return (
    <Sheet title={`Store ${entry.name} · ${entry.qty} MT`} onClose={onClose}>

      {/* Advisory-suggested cold storage — the single match from this crop's advisory */}
      <p className="text-[11px] font-medium uppercase tracking-wide t-sub mb-2">
        Advisory-Suggested Cold Storage
      </p>
      <div className="rounded-xl border border-amber-500 bg-amber-500/5 p-3 mb-4">
        <div className="flex items-center justify-between mb-1">
          <div className="text-sm font-semibold t-text">{facility.facility || "Cold Storage"}</div>
          <span className="text-[10px] font-medium text-amber-500 bg-amber-500/10 rounded-full px-2 py-0.5 flex items-center gap-1">
            <Star className="h-2.5 w-2.5" /> From Advisory
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs t-sub">
          {facility.rate     && <span>{facility.rate}</span>}
          {facility.avail    && <span>{facility.avail}</span>}
          {facility.period   && <span>{facility.period}</span>}
          {facility.distance && <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{facility.distance}</span>}
          {facility.address  && <span>{facility.address}</span>}
          {facility.contact  && <span className="flex items-center gap-1"><Phone className="h-3 w-3" />{facility.contact}</span>}
        </div>
      </div>

      {/* Transport */}
      <p className="text-[11px] font-medium uppercase tracking-wide t-sub mb-2">
        Transport {transports.length === 0 ? "(none registered)" : `(${transports.length} available)`}
      </p>
      {transports.length === 0 ? (
        <div className="rounded-xl border t-border t-card p-3 mb-4 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 text-amber-400 flex-shrink-0" />
          <span className="text-xs t-sub">No transporters registered yet. You can arrange your own transport.</span>
        </div>
      ) : (
        <div className="space-y-2 mb-4">
          {(Array.isArray(transports) ? transports : []).map((t, i) => (
            <button key={i} onClick={() => setPickedTransport(i)}
              className={`w-full rounded-xl border p-3 text-left transition ${pickedTransport===i ? "border-sky-500 bg-sky-500/5" : "t-border t-card"}`}>
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium t-text">{t.name || t.ownerName}</div>
                {i===0 && <span className="text-[10px] font-medium text-sky-500 bg-sky-500/10 rounded-full px-2 py-0.5">Best match</span>}
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs t-sub">
                {t.vehicle   && <span>{t.vehicle}</span>}
                {t.rate      && <span>₹{t.rate}/MT/km</span>}
                {t.district  && <span className="flex items-center gap-1"><MapPin className="h-3 w-3" />{t.district}</span>}
                {t.ownerPhone && <span className="flex items-center gap-1"><Phone className="h-3 w-3" />{t.ownerPhone}</span>}
              </div>
            </button>
          ))}
        </div>
      )}
      <Field label="Pickup Date">
        <TextInput type="date" value={pickupDate} onChange={(e) => setPickupDate(e.target.value)}/>
      </Field>


      {/* Duration picker */}
      <div className="flex items-center justify-between t-card border t-border rounded-xl p-3 mb-3">
        <span className="text-xs font-medium t-sub">Storage duration</span>
        <div className="flex items-center gap-3">
          <button onClick={() => setDays((d) => Math.max(7,d-7))} className="rounded-full border t-border p-1.5 t-text hover:opacity-70 transition"><Minus className="h-3.5 w-3.5" /></button>
          <span className="w-16 text-center text-sm font-semibold t-text">{days} days</span>
          <button onClick={() => setDays((d) => Math.min(180,d+7))} className="rounded-full border t-border p-1.5 t-text hover:opacity-70 transition"><Plus className="h-3.5 w-3.5" /></button>
        </div>
      </div>

      {/* Cost summary */}
      <div className="rounded-xl t-card border t-border p-3 flex items-center justify-between mb-3">
        <div>
          <div className="text-xs t-sub">Estimated storage cost</div>
          <div className="text-[11px] t-muted">{facility.rate || "Rate from advisory"} × {entry.qty} MT × {days}d</div>
        </div>
        <div className="text-lg font-semibold text-amber-500">{fmtINR(cost)}</div>
      </div>

      <PrimaryButton className="!bg-amber-500 hover:!bg-amber-400" loading={submitting} disabled={submitting || !facility}
        onClick={async () => {
          setSubmitting(true);
          const bookingId = "BK-" + Math.random().toString(36).slice(2,8).toUpperCase();
          const deal = { id:bookingId, facility: facility?.facility || "Storage", days, cost };
          try {
            // Send the booking through the dedicated booking bridge flow so the
            // backend can record it against this Farmer ID + storage and block
            // those days going forward.
            await sendToFlow("booking", {
              FarmerID:    facility?.farmerId || "",
              SellStore:   facility?.facility || "",
              StorageDays: String(days),
              Confirm:     "yes",
            });
          } catch (err) { console.error("[KrishiSetu] Bridge error:", err); }
          const bookings = await getTransportBookings();
          transporter && (bookings.push({ transporter: transporter.name, startDate: pickupDate, endDate: new Date(new Date(pickupDate).setDate(new Date(pickupDate).getDate() + Number(transporter.avDays || 1))).toISOString().split("T")[0] }), saveTransportBookings(bookings));
          setDone(deal);
          onConfirm(deal);
          setSubmitting(false);
        }}>
        {submitting ? "Booking…" : "Confirm booking"}
      </PrimaryButton>
    </Sheet>
  );
}

function AdvisorySheet({ entry, onClose }) {
  const advisory = entry._advisory || buildAdvisory(entry);

  return (
    <Sheet title="Crop Advisory" onClose={onClose}>
      <div className="space-y-3">
        <div className="rounded-xl border t-border p-3 flex items-center gap-3">
          <div className="text-2xl">{entry.emoji}</div>
          <div>
            <div className="font-semibold t-text">{entry.name} · {entry.qty} MT</div>
            <div className="text-xs t-sub">{entry.village ? entry.village + " · " : ""}{entry.district}</div>
          </div>
          <VerdictBadge verdict={advisory.verdict} />
        </div>
        <div className="rounded-xl border t-border p-3 flex items-center justify-between">
          <span className="text-xs t-sub">Current price estimate</span>
          <span className="text-base font-semibold t-text">{fmtINR(advisory.price)}/quintal</span>
        </div>
        <div className="rounded-xl border t-border p-3 text-sm t-text leading-relaxed">
          {advisory.reason}
        </div>
      </div>
    </Sheet>
  );
}
/* ─────────────────────────────────────────────────────────────────────────── */
/* Add crop modal                                                               */
/* ─────────────────────────────────────────────────────────────────────────── */

function AddCropModal({ onClose, onAdd, userDistrict, user }) {
  const [crop,             setCrop]             = useState("");
  const [qty,              setQty]              = useState("");
  const [district,         setDistrict]         = useState(userDistrict || "");
  const [village,          setVillage]          = useState("");
  const [daysUntilHarvest, setDaysUntilHarvest] = useState("0");
  const [notes,            setNotes]            = useState("");
  const [submitting,       setSubmitting]       = useState(false);

  const valid = crop && qty && Number(qty) > 0 && district && daysUntilHarvest !== "";

  async function submit() {
    console.log("crop",crop)
  setSubmitting(true);
  const entry = {
    id: crop + "-" + district + "-" + Date.now(),
    name: crop, emoji: cropMeta(crop).emoji, qty: Number(qty), district, village,
    daysUntilHarvest: Number(daysUntilHarvest), status: "pending",
    addedAt: new Date().toISOString(),
  };
  try {
    const result = await sendToFlow("farmer", {
      name: user?.name || "", phone: user?.mobile || "",
      crop, qty: String(qty), district, village,
      days: String(daysUntilHarvest), notes, confirm: "yes",
    });
    // store the bridgeId on the entry so AdvisorySheet can use it
    console.log("FULL BRIDGE RESPONSE", result);
    console.log("ERROR MESSAGE =", result?.ErrorMessage);

    entry.bridgeId = result?.ErrorMessage || "";

    console.log("ENTRY BEFORE ONADD =", entry);
  } catch (err) { 
    console.error("[KrishiSetu] Bridge error:", err); 
  }
  console.log("ENTRY BEFORE ONADD", entry);
 
  onAdd(entry);  // ← moved after sendToFlow so bridgeId is included
  console.log("ADDING ENTRY", entry);  
  onClose();
}
  return (
    <Sheet title="Add a crop" onClose={onClose}>
      <Field label="Crop" required>
        <Select value={crop} onChange={(e) => setCrop(e.target.value)}>
          <option value="">Select crop</option>
          {CROP_CATALOG.map((c) => <option key={c.name}>{c.name}</option>)}
        </Select>
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Quantity (MT)" required>
          <TextInput type="number" min="0.1" step="0.1" placeholder="5" value={qty} onChange={(e) => setQty(e.target.value)} />
        </Field>
        <Field label="Days to harvest" required>
          <TextInput type="number" min="0" placeholder="0 = ready" value={daysUntilHarvest} onChange={(e) => setDaysUntilHarvest(e.target.value)} />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="District" required>
          <Select value={district} onChange={(e) => setDistrict(e.target.value)}>
            <option value="">Select</option>
            {KA_DISTRICTS.map((d) => <option key={d}>{d}</option>)}
          </Select>
        </Field>
        <Field label="Village / Taluk">
          <TextInput placeholder="Kolar Taluk" value={village} onChange={(e) => setVillage(e.target.value)} />
        </Field>
      </div>
      <Field label="Notes">
        <TextArea placeholder="Variety, quality grade, organic…" value={notes} onChange={(e) => setNotes(e.target.value)} />
      </Field>
      <PrimaryButton disabled={!valid || submitting} loading={submitting} onClick={submit}>
        {submitting ? "Adding…" : "Add crop"}
      </PrimaryButton>
    </Sheet>
  );
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Business registration form                                                   */
/* ─────────────────────────────────────────────────────────────────────────── */

function BizForm({ role, onClose, onSubmitted }) {
  const [vals,       setVals]       = useState({});
  const [submitting, setSubmitting] = useState(false);
  const set = (k) => (e) => setVals((v) => ({ ...v, [k]: e.target.value }));

  const titles = { storage:"List cold storage facility", transport:"Register vehicle / fleet", trader:"Register as buyer / trader" };

  async function submit() {
    setSubmitting(true);
    let payload = {}, label = "", savedData = {};
    if (role==="storage") {
      payload    = { facility:vals.facility, operator:vals.operator, phone:vals.phone, district:vals.district, address:vals.address, cap:vals.cap, fromDays:vals.fromDays||"0", duration:vals.duration, crops:vals.crops, rate:vals.rate, notes:vals.notes, confirm:"yes" };
      label      = vals.facility;
      savedData  = { facility:vals.facility, district:vals.district, cap:vals.cap, rate:vals.rate, crops: vals.crops, phone: vals.phone };
    } else if (role==="transport") {
      payload    = { name:vals.name, driver:vals.driver||vals.name, phone:vals.phone, district:vals.district, vehicle:vals.vehicle, cap:vals.cap, refrig:vals.refrig||"no", fromDays:vals.fromDays||"0", avDays:vals.avDays, maxDist:vals.maxDist, rate:vals.rate, opDists:vals.opDists, notes:vals.notes, confirm:"yes" };
      label      = vals.name;
      savedData  = { name:vals.name, vehicle:vals.vehicle, district:vals.district, rate:vals.rate, cap: vals.cap, phone: vals.phone, avDays:vals.avDays};
    } else {
      payload    = { company:vals.company, phone:vals.phone, district:vals.district, crops:vals.crops, buyDists:vals.buyDists, confirm:"yes" };
      label      = vals.company;
      savedData  = { company:vals.company, district:vals.district, crops:vals.crops };
    }
    try {
      await sendToFlow(role, payload);
      onSubmitted({ ok:true, label, role, savedData });
    } catch (err) {
      console.error("[KrishiSetu] Bridge error (" + role + "):", err);
      onSubmitted({ ok:false, label, role, savedData });
    }
    onClose();
  }

  return (
    <Sheet title={titles[role]} onClose={onClose}>
      {role==="storage" && <>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Facility name" required><TextInput placeholder="AgroFreeze Kolar" onChange={set("facility")} /></Field>
          <Field label="Operator name" required><TextInput placeholder="Suresh Reddy" onChange={set("operator")} /></Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Phone" required><TextInput type="tel" placeholder="9876543210" onChange={set("phone")} /></Field>
          <Field label="District" required>
            <Select onChange={set("district")}><option value="">Select</option>{KA_DISTRICTS.map((d) => <option key={d}>{d}</option>)}</Select>
          </Field>
        </div>
        <Field label="Address" required><TextInput placeholder="NH 75, Kolar" onChange={set("address")} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Capacity (MT)" required><TextInput type="number" placeholder="120" onChange={set("cap")} /></Field>
          <Field label="Rate ₹/MT/day" required><TextInput type="number" placeholder="150" onChange={set("rate")} /></Field>
        </div>
        <Field label="Duration available (days)" required><TextInput type="number" placeholder="30" onChange={set("duration")} /></Field>
        <Field label="Crops supported" required><TextInput placeholder="Tomato, Onion — or All" onChange={set("crops")} /></Field>
        <Field label="Notes"><TextArea placeholder="Temp range, loading bay, certifications…" onChange={set("notes")} /></Field>
      </>}

      {role==="transport" && <>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Name / Company" required><TextInput placeholder="Raju Transport" onChange={set("name")} /></Field>
          <Field label="Driver name"><TextInput placeholder="Same as above if blank" onChange={set("driver")} /></Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Phone" required><TextInput type="tel" placeholder="9876543210" onChange={set("phone")} /></Field>
          <Field label="Base district" required>
            <Select onChange={set("district")}><option value="">Select</option>{KA_DISTRICTS.map((d) => <option key={d}>{d}</option>)}</Select>
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Vehicle type" required>
            <Select onChange={set("vehicle")}><option value="">Select</option>{VEHICLES.map((v) => <option key={v}>{v}</option>)}</Select>
          </Field>
          <Field label="Capacity (MT)" required><TextInput type="number" placeholder="5" onChange={set("cap")} /></Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Max distance (km)" required><TextInput type="number" placeholder="200" onChange={set("maxDist")} /></Field>
          <Field label="Rate ₹/MT/km" required><TextInput type="number" placeholder="2.5" onChange={set("rate")} /></Field>
        </div>
        <Field label="Available days" required><TextInput type="number" placeholder="7" onChange={set("avDays")} /></Field>
        <Field label="Operating districts" required><TextInput placeholder="Kolar, Tumkur — or All Karnataka" onChange={set("opDists")} /></Field>
        <Field label="Notes"><TextArea placeholder="Vehicle number, multi-trip, refrigerated?" onChange={set("notes")} /></Field>
      </>}

      {role==="trader" && <>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Company name" required><TextInput placeholder="Kolar Agro Traders" onChange={set("company")} /></Field>
          <Field label="Phone" required><TextInput type="tel" placeholder="9876543210" onChange={set("phone")} /></Field>
        </div>
        <Field label="Base district" required>
          <Select onChange={set("district")}><option value="">Select</option>{KA_DISTRICTS.map((d) => <option key={d}>{d}</option>)}</Select>
        </Field>
        <Field label="Crops you trade" required><TextInput placeholder="Tomato, Onion — or All crops" onChange={set("crops")} /></Field>
        <Field label="Districts you buy from" required><TextInput placeholder="Kolar, Tumkur — or All Karnataka" onChange={set("buyDists")} /></Field>
      </>}

      <PrimaryButton disabled={submitting} loading={submitting} onClick={submit}>
        {submitting ? "Submitting…" : "Submit registration"}
      </PrimaryButton>
    </Sheet>
  );
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Activity tab — role-aware                                                    */
/* ─────────────────────────────────────────────────────────────────────────── */

const ACTIVITY_META = {
  crop:      { icon:Sprout,       bg:"bg-emerald-500/10", color:"text-emerald-500", label:"Crop added"       },
  sale:      { icon:ShoppingCart, bg:"bg-emerald-500/10", color:"text-emerald-500", label:"Sale"             },
  storage:   { icon:Warehouse,    bg:"bg-amber-500/10",   color:"text-amber-500",   label:"Storage booking"  },
  transport: { icon:Truck,        bg:"bg-sky-500/10",     color:"text-sky-500",     label:"Trip"             },
  trade:     { icon:Building2,    bg:"bg-violet-500/10",  color:"text-violet-500",  label:"Trade"            },
  business:  { icon:Building2,    bg:"bg-sky-500/10",     color:"text-sky-500",     label:"Registration"     },
};

// Per-role: which filter tabs to show and what the empty state says
const ROLE_ACTIVITY_CONFIG = {
  farmer: {
    tabs: [
      { key:"all",     label:"All"     },
      { key:"sale",    label:"Sales"   },
      { key:"storage", label:"Storage" },
      { key:"crop",    label:"Crops"   },
    ],
    emptyIcon: Sprout,
    emptyTitle: "No activity yet",
    emptySub:   "Add a crop to get started — sell or store it to see actions here",
  },
  storage: {
    tabs: [
      { key:"all",      label:"All"          },
      { key:"storage",  label:"Bookings"     },
      { key:"business", label:"Registrations"},
    ],
    emptyIcon: Warehouse,
    emptyTitle: "No bookings yet",
    emptySub:   "List your cold storage facility to start receiving farmer bookings",
  },
  transport: {
    tabs: [
      { key:"all",       label:"All"          },
      { key:"transport", label:"Trips"        },
      { key:"business",  label:"Registrations"},
    ],
    emptyIcon: Truck,
    emptyTitle: "No trips yet",
    emptySub:   "Register your vehicle to start receiving transport requests",
  },
  trader: {
    tabs: [
      { key:"all",      label:"All"          },
      { key:"trade",    label:"Trades"       },
      { key:"business", label:"Registrations"},
    ],
    emptyIcon: Building2,
    emptyTitle: "No trades yet",
    emptySub:   "Register as a buyer to start connecting with farmers",
  },
};

// accent color per role for the summary chips
const ROLE_ACCENT = {
  farmer:    { count_bg:"bg-emerald-500/10", count_text:"text-emerald-500" },
  storage:   { count_bg:"bg-amber-500/10",   count_text:"text-amber-500"   },
  transport: { count_bg:"bg-sky-500/10",     count_text:"text-sky-500"     },
  trader:    { count_bg:"bg-violet-500/10",  count_text:"text-violet-500"  },
};

function ActivitySummaryChips({ activity, activeRoles }) {
  // Show a compact count chip per role that has activity
  const counts = {};
  activity.forEach((a) => {
    const roleOf = a.type === "crop" || a.type === "sale" || a.type === "storage" ? "farmer"
                 : a.type === "transport" ? "transport"
                 : a.type === "trade"     ? "trader"
                 : "farmer"; // business registrations — attribute to the user's first active role
    counts[roleOf] = (counts[roleOf] || 0) + 1;
  });

  const chips = activeRoles
    .map((rk) => ({ rk, count: counts[rk] || 0 }))
    .filter(({ count }) => count > 0);

  if (chips.length === 0) return null;

  return (
    <div className="flex gap-2 mb-4 flex-wrap">
      {chips.map(({ rk, count }) => {
        const r = ALL_ROLES.find((x) => x.key === rk);
        const acc = ROLE_ACCENT[rk] || ROLE_ACCENT.farmer;
        if (!r) return null;
        return (
          <div key={rk} className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${acc.count_bg} ${acc.count_text}`}>
            <r.Icon className="h-3 w-3" />
            {r.label} · {count} action{count !== 1 ? "s" : ""}
          </div>
        );
      })}
    </div>
  );
}

function ActivityTab({ activity, user }) {
  const activeRoles   = user?.activeRoles || [user?.role || "farmer"];
  // Primary role drives the default tab set; if multi-role, show "all" tabs merged
  const primaryRole   = user?.role || "farmer";
  const config        = ROLE_ACTIVITY_CONFIG[primaryRole] || ROLE_ACTIVITY_CONFIG.farmer;

  // Build merged tab list when user has multiple roles
  const allTabKeys = new Set(["all"]);
  activeRoles.forEach((r) => {
    (ROLE_ACTIVITY_CONFIG[r]?.tabs || []).forEach((t) => allTabKeys.add(t.key));
  });
  const TAB_ORDER = ["all","crop","sale","storage","transport","trade","business"];
  const TAB_LABELS = {
    all:"All", crop:"Crops", sale:"Sales", storage:"Storage",
    transport:"Trips", trade:"Trades", business:"Registrations",
  };
  const visibleTabs = TAB_ORDER
    .filter((k) => allTabKeys.has(k))
    .map((k) => ({ key:k, label:TAB_LABELS[k] }));

  const [filter, setFilter] = useState("all");
  const filtered = filter === "all" ? activity : activity.filter((a) => a.type === filter);

  const EmptyIcon = config.emptyIcon;

  // Role-specific empty state copy per active filter
  function emptyMessage() {
    if (filter === "all") return { title: config.emptyTitle, sub: config.emptySub };
    const labels = { crop:"crops", sale:"sales", storage:"storage bookings", transport:"trips", trade:"trades", business:"registrations" };
    return { title: `No ${labels[filter] || "activity"} yet`, sub: "Actions you take will appear here" };
  }
  const { title: emptyTitle, sub: emptySub } = emptyMessage();

  return (
    <div className="px-4 pt-4 pb-6">
      {/* Header */}
      <div className="mb-4">
        <h2 className="text-lg font-bold t-text">Activity</h2>
        <p className="text-sm t-sub">Everything you've done across all your roles.</p>
      </div>

      {/* Role-activity summary chips */}
      {activeRoles.length > 1 && activity.length > 0 && (
        <ActivitySummaryChips activity={activity} activeRoles={activeRoles} />
      )}

      {/* Filter tabs */}
      <div className="flex gap-1 mb-4 rounded-xl t-chip border t-border p-1 overflow-x-auto scrollbar-hide">
        {visibleTabs.map(({ key, label }) => (
          <button key={key} onClick={() => setFilter(key)}
            className={`flex-shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium transition ${filter === key ? "t-card t-text shadow" : "t-sub"}`}>
            {label}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="text-center py-16 t-muted">
          <EmptyIcon className="mx-auto h-8 w-8 mb-2 opacity-40" />
          <p className="text-sm font-medium">{emptyTitle}</p>
          <p className="text-xs mt-1 opacity-60 max-w-[220px] mx-auto leading-relaxed">{emptySub}</p>
        </div>
      ) : (
        <div className="rounded-2xl border t-border t-card divide-y t-divide">
          {filtered.map((a) => {
            const meta = ACTIVITY_META[a.type] || ACTIVITY_META.business;
            const Icon = meta.icon;
            // Badge label shown on the right (type pill)
            const pillColors = {
              crop:      "bg-emerald-500/10 text-emerald-500",
              sale:      "bg-emerald-500/10 text-emerald-500",
              storage:   "bg-amber-500/10 text-amber-500",
              transport: "bg-sky-500/10 text-sky-500",
              trade:     "bg-violet-500/10 text-violet-500",
              business:  "bg-zinc-500/10 text-zinc-400",
            };
            return (
              <div key={a.id} className="flex items-center gap-3 p-3.5">
                <div className={`flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg ${meta.bg}`}>
                  <Icon className={`h-4 w-4 ${meta.color}`} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium t-text truncate">{a.label}</div>
                  <div className="text-xs t-sub truncate">{a.sub}</div>
                </div>
                <div className="flex flex-col items-end gap-1 flex-shrink-0">
                  <span className={`text-[10px] font-medium rounded-full px-2 py-0.5 ${pillColors[a.type] || pillColors.business}`}>
                    {meta.label}
                  </span>
                  <span className="text-[11px] t-muted">
                    {new Date(a.at).toLocaleDateString("en-IN",{day:"numeric",month:"short"})}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Profile tab                                                                  */
/* ─────────────────────────────────────────────────────────────────────────── */

function ProfileTab({ user, onOpenBiz, onLogout }) {
  const initials   = user.name.split(" ").map((w) => w[0]).join("").slice(0,2).toUpperCase();
  const activeRoles = user.activeRoles || [user.role || "farmer"];
  const primaryRole = ALL_ROLES.find((r) => r.key === user.role) || ALL_ROLES[0];
  const PrimaryIcon = primaryRole.Icon;
  const otherRoles  = ALL_ROLES.filter((r) => !activeRoles.includes(r.key));

  return (
    <div className="px-4 pt-4 pb-6">
      <div className="rounded-2xl border t-border t-card p-4 flex items-center gap-3 mb-5">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/15 border border-emerald-500/30 text-sm font-bold text-emerald-500">
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold t-text">{user.name}</div>
          <div className="text-xs t-sub flex items-center gap-1"><Phone className="h-3 w-3" />{user.mobile}</div>
          {user.district && <div className="text-xs t-muted flex items-center gap-1"><MapPin className="h-3 w-3" />{user.district}</div>}
        </div>
        <div className={`flex items-center gap-1.5 rounded-full border t-border px-2.5 py-1 ${primaryRole.bg}`}>
          <PrimaryIcon className={`h-3.5 w-3.5 ${primaryRole.color}`} />
          <span className={`text-[10px] font-medium ${primaryRole.color}`}>{primaryRole.label}</span>
        </div>
      </div>

      {/* Active roles badges */}
      {activeRoles.length > 1 && (
        <>
          <div className="text-[11px] font-medium uppercase tracking-wide t-sub mb-2">Your active roles</div>
          <div className="flex flex-wrap gap-2 mb-5">
            {activeRoles.map((rk) => {
              const r = ALL_ROLES.find((x) => x.key === rk);
              if (!r) return null;
              return (
                <span key={rk} className={`inline-flex items-center gap-1.5 rounded-full border t-border px-2.5 py-1 ${r.bg}`}>
                  <r.Icon className={`h-3 w-3 ${r.color}`} />
                  <span className={`text-[10px] font-medium ${r.color}`}>{r.label}</span>
                </span>
              );
            })}
          </div>
        </>
      )}

      {/* Register as additional roles */}
      {otherRoles.length > 0 && (
        <>
          <div className="text-[11px] font-medium uppercase tracking-wide t-sub mb-2">Also register as</div>
          <div className="rounded-2xl border t-border t-card divide-y t-divide mb-5">
            {otherRoles.map(({ key, label, Icon, color, bg }) => (
              <button key={key} onClick={() => onOpenBiz(key)}
                className="w-full flex items-center gap-3 p-3.5 text-left hover:opacity-80 transition">
                <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${bg}`}>
                  <Icon className={`h-4 w-4 ${color}`} />
                </div>
                <div className="flex-1 text-sm font-medium t-text">{label}</div>
                <div className="flex items-center gap-1.5">
                  <span className="text-xs t-muted">Register</span>
                  <ChevronRight className="h-4 w-4 t-muted" />
                </div>
              </button>
            ))}
          </div>
        </>
      )}

      <div className="rounded-2xl border t-border t-card divide-y t-divide mb-5">
        <button onClick={() => alert("🆘 KritiSetu Help & Support\n\n" + "Need assistance?\n\n" + "• Farmer Registration Issues\n" +"• Crop Advisory Queries\n" +"• Cold Storage Booking Support\n" +"• Transport Booking Assistance\n" +"• Market Price Information\n\n" +"Contact: support@kritisetu.com\n" +"Helpline: +91 XXXXX XXXXX")} 
          className="w-full flex items-center gap-3 p-3.5 text-left hover:opacity-80 transition">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg t-chip">
            <HelpCircle className="h-4 w-4 t-sub" />
          </div>
          <div className="flex-1 text-sm font-medium t-text">Help &amp; support</div>
          <ChevronRight className="h-4 w-4 t-muted" />
        </button>
      </div>

      <GhostButton onClick={onLogout} className="border-rose-500/30 !text-rose-500 hover:!bg-rose-500/10">
        <LogOut className="h-4 w-4" /> Log out
      </GhostButton>
      <p className="mt-4 text-center text-[10px] t-muted">KrishiSetu · Karnataka Agri Platform · v3.0</p>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Header                                                                       */
/* ─────────────────────────────────────────────────────────────────────────── */

function Header({ user, onLogout, dark, onToggleDark }) {
  const initials =user?.name? user.name.split(" ").map((w) => w[0]).join("").slice(0, 2).toUpperCase() : "U";
  const [open, setOpen] = useState(false);

  return (
    <div className="flex items-center justify-between px-4 py-3 border-b t-nav t-border sticky top-0 z-20 backdrop-blur">
      <div className="flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/10 border border-emerald-500/30">
          <Leaf className="h-4 w-4 text-emerald-500" />
        </div>
        <span className="text-sm font-bold t-text tracking-tight">KrishiSetu</span>
      </div>
      <div className="relative">
        <button onClick={() => setOpen((v) => !v)}
          className="flex h-8 w-8 items-center justify-center rounded-full t-chip text-xs font-semibold t-text hover:opacity-80 transition">
          {initials}
        </button>
        {open && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setOpen(false)} />
            <div className="absolute right-0 mt-2 w-48 rounded-xl border t-border t-card t-shadow z-20 overflow-hidden">
              <button
                onClick={() => { onToggleDark(); setOpen(false); }}
                className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm t-text hover:opacity-80 transition">
                {dark
                  ? <><Sun className="h-4 w-4 text-amber-400" /> Switch to light mode</>
                  : <><Moon className="h-4 w-4 text-sky-500" /> Switch to dark mode</>
                }
              </button>
              <div className="border-t t-border" />
              <button onClick={() => { setOpen(false); onLogout(); }}
                className="w-full flex items-center gap-2.5 px-4 py-2.5 text-sm text-rose-500 hover:opacity-80 transition">
                <LogOut className="h-4 w-4" /> Log out
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function BottomNav({ tab, setTab }) {
  const items = [["home","Home",HomeIcon],["activity","Activity",HistoryIcon],["profile","Profile",User]];
  return (
    <div className="flex border-t t-nav t-border sticky bottom-0 z-20 backdrop-blur">
      {items.map(([key,label,Icon]) => (
        <button key={key} onClick={() => setTab(key)}
          className={`flex-1 flex flex-col items-center gap-1 py-2.5 transition ${tab===key ? "text-emerald-500" : "t-muted hover:opacity-80"}`}>
          <Icon className="h-5 w-5" />
          <span className="text-[10px] font-medium">{label}</span>
        </button>
      ))}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────── */
/* Root                                                                         */
/* ─────────────────────────────────────────────────────────────────────────── */

export default function App() {
  const [dark,        setDark]        = useState(true);
  const [user,        setUser]        = useState(null);
  const [tab,         setTab]         = useState("home");
  const [crops,       setCrops]       = useState([]);
  useEffect(() => {
    console.log("CROPS STATE CHANGED", crops);
  }, [crops]);
  const [activity,    setActivity]    = useState([]);
  const [bizData,     setBizData]     = useState({});   // { storage:{…}, transport:{…}, trader:{…} }
  const [storageBookings, setStorageBookings] = useState([]);
  const [sellTarget,  setSellTarget]  = useState(null);
  const [storeTarget, setStoreTarget] = useState(null);
  const [showAddCrop, setShowAddCrop] = useState(false);
  const [bizRole,     setBizRole]     = useState(null);
  const [toast,       setToast]       = useState(null);
  const [advisoryData, setAdvisoryData] = useState(null);

  // Inject theme CSS once
  useEffect(() => { injectThemeStyle(); }, []);

  // Apply theme to root element
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    async function saveData() {

      if (!user?.mobile)
        return;

      await saveUserData(
        user.mobile,
        "crops",
        crops
      );
    }

    saveData();
  }, [crops, user]);

  useEffect(() => {
    async function saveData() {

      if (!user?.mobile)
        return;

      await saveUserData(
        user.mobile,
        "activity",
        activity
      );
    }

    saveData();
  }, [activity, user]);

  useEffect(() => {
    async function saveData() {

      if (!user?.mobile)
        return;

      await saveUserData(
        user.mobile,
        "bizdata",
        bizData
      );
    }

  saveData();
}, [bizData, user]);

  useEffect(() => {
    if (!toast) return;
    const id = setTimeout(() => setToast(null), 3000);
    return () => clearTimeout(id);
  }, [toast]);

  function showToast(msg, type="info") { setToast({ msg, type }); }
  function logAct(type, label, sub) {
    setActivity((a) => [{ id: Date.now().toString(36)+Math.random().toString(36).slice(2), type, label, sub, at: new Date().toISOString() }, ...a]);
  }

  async function handleLogin(profile) {
    try {
      if (!profile?.mobile) {
        console.error("Invalid profile passed to handleLogin", profile);
        return;
      }
      const data = await loadUserData(profile.mobile);
      console.log("LOGIN USER =", profile.mobile);
      console.log("LOGIN DATA =", data);

      if (!profile.activeRoles)
        profile.activeRoles = [profile.role || "farmer"];

      setUser(profile);
      setCrops(data?.crops || []);
      setActivity(data?.activity || []);
      setBizData(data?.bizData || {});
      setStorageBookings(data?.storageBookings || []);
      setTab("home");

    } catch (err) {
      console.error("LOGIN ERROR", err);
    }
  }
  function handleLogout() { setUser(null); setCrops([]); setActivity([]); setBizData({}); setTab("home"); }

  function handleAddCrop(entry) {
    console.log("HANDLE ADD CROP ENTRY =", entry);

    setCrops((c) => [...c, entry]);

    logAct(
      "crop",
      `Added ${entry.name} · ${entry.qty} MT`,
      `${entry.village ? entry.village + " · " : ""}${entry.district}`
    );

    showToast("Crop added", "success");
  }

  function handleSellConfirm(entry, deal) {
    setCrops((cs) => cs.map((c) => c.id===entry.id ? { ...c, status:"sold", deal } : c));
    logAct("sale", `Sold ${entry.name} · ${entry.qty} MT`, `${deal.buyer} · ${fmtINR(deal.total)}`);
    setSellTarget(null);
  }

  async function handleStoreConfirm(entry, deal) {

    const booking = {
      id: Date.now().toString(),

      farmerName: user.name,
      farmerMobile: user.mobile,

      crop: entry.name,
      qty: entry.qty,

      district: entry.district,

      facility: deal.facility,

      storageMobile: deal.phone,

      days: deal.days,

      status: "pending",

      createdAt: new Date().toISOString()
    };

    setCrops((cs) =>
      cs.map((c) =>
        c.id === entry.id
          ? { ...c, status: "stored", deal }
          : c
      )
    );

    logAct(
      "storage",
      `Stored ${entry.name} · ${entry.qty} MT`,
      `${deal.facility} · ${deal.days} days`
    );

    const existing =
      (await loadUserData(deal.phone))
        ?.storageBookings || [];

    await saveUserData(
      deal.phone,
      "storageBookings",
      [...existing, booking]
    );

    console.log("STORAGE BOOKING SAVED");

    setStoreTarget(null);

    showToast(
      "Storage request sent!",
      "success"
    );
  }


  async function handleBizSubmitted({ ok, label, role, savedData }) {
  if (ok) {

    const newRoles = user.activeRoles.includes(role)
      ? user.activeRoles
      : [...user.activeRoles, role];

    const updatedUser = {
      ...user,
      activeRoles: newRoles,
    };

    setUser(updatedUser);

    await saveUserData(
      updatedUser.mobile,
      "profile",
      updatedUser
    );

    let updatedBizData;

    if (role === "transport") {
      updatedBizData = {
        ...bizData,
        transport: [
          ...(Array.isArray(bizData.transport)
            ? bizData.transport
            : bizData.transport
            ? [bizData.transport]
            : []),
          savedData,
        ],
      };
    } else if (role === "storage") {
      updatedBizData = {
        ...bizData,
        storage: [
          ...(Array.isArray(bizData.storage)
            ? bizData.storage
            : bizData.storage
            ? [bizData.storage]
            : []),
          savedData,
        ],
      };
    } else {
      updatedBizData = {
        ...bizData,
        [role]: savedData,
      };
    }

    setBizData(updatedBizData);

    await saveUserData(
      user.mobile,
      "bizdata",
      updatedBizData
    );
  }

  logAct(
    "business",
    ok ? `Registered as ${label}` : `Registration failed for ${label}`,
    ok ? "Submitted to KrishiSetu" : "Check connection & try again"
  );

  showToast(
    ok ? "Registration submitted!" : "Could not submit — try again",
    ok ? "success" : "error"
  );
}
  // Trigger biz form for a role (from home panel CTA or profile tab)
  function handleRegisterRole(role) { setBizRole(role); }

  return (
    <div className="min-h-screen t-page flex justify-center font-sans">
      <div className="w-full max-w-md min-h-screen t-page relative flex flex-col">
        {/* Ambient glow — subtle in both themes */}
        <div className="pointer-events-none fixed -top-24 right-0 w-80 h-80 bg-emerald-500/5 rounded-full blur-3xl" />
        <div className="pointer-events-none fixed bottom-0 -left-16 w-64 h-64 bg-emerald-500/5 rounded-full blur-3xl" />

        <div className="relative z-10 flex flex-col min-h-screen t-text">
          {!user ? (
            <AuthScreen onLogin={handleLogin} />
          ) : (
            <>
              <Header user={user} onLogout={handleLogout} dark={dark} onToggleDark={() => setDark((d) => !d)} />
              <div className="flex-1 overflow-y-auto">
                {tab==="home" && (
                  <HomeTab
                    user={user} crops={crops} bizData={bizData}
                    onAddCrop={() => setShowAddCrop(true)}
                    onSell={(e,a) => setSellTarget({entry:e,advisory:a})}
                    onStore={(e, a, advisoryStorage) => setStoreTarget({ entry:e, advisory:a, advisoryStorage })}
                    onRegisterRole={handleRegisterRole}
                    onAdvisory={(entry, advisory) => setAdvisoryData({ ...entry, _advisory: advisory })}
                  />
                )}
                {tab==="activity" && <ActivityTab activity={activity} />}
                {tab==="profile"  && <ProfileTab  user={user} onOpenBiz={handleRegisterRole} onLogout={handleLogout} />}
              </div>
              <BottomNav tab={tab} setTab={setTab} />
            </>
          )}
        </div>

        {showAddCrop && <AddCropModal onClose={() => setShowAddCrop(false)} onAdd={handleAddCrop} userDistrict={user?.district} user={user} />}
        {sellTarget  && <SellSheet   entry={sellTarget.entry} advisory={sellTarget.advisory} user={user} onClose={() => setSellTarget(null)} onConfirm={(deal) => handleSellConfirm(sellTarget.entry, deal)} />}
        {storeTarget && <StoreSheet  entry={storeTarget.entry} advisoryStorage={storeTarget.advisoryStorage} user={user} onClose={() => setStoreTarget(null)} onConfirm={(deal) => handleStoreConfirm(storeTarget.entry, deal)} />}
        {advisoryData && (<AdvisorySheet entry={advisoryData} onClose={() => setAdvisoryData(null)}/>)}
        {bizRole     && <BizForm     role={bizRole} onClose={() => setBizRole(null)} onSubmitted={handleBizSubmitted} />}
        {toast && <Toast message={toast.msg} type={toast.type} />}
      </div>
    </div>
  );
}

export const generateReport = async (payload, api) => {
    try {
        // ForumDetails['ServerID'] = TSServerID;
        return axios({
            method: "post",
            url: serverID + api,
            data: payload,
            headers: { 'Content-Type': 'multipart/form-data' },
        })
            .then(function (response) {
                return response.data;
            })
            .catch(function (error) {
                return error;
            });
    } catch (e) { }
  }

const fetchTaskID = async () => {
    try {
      // const templateData = JSON.parse(decodeWithBase64(localStorage.getItem(TaskManagementForumId)));
      // const userProfile = JSON.parse(decodeWithBase64(localStorage.getItem("userProfile")));
      const templateName = "FarmerFLow";
      const forumID = "8620c2d6-7b38-429b-9d95-ce81806fcf79";
      // const AdminTemplateDetails = templateData['AdminFlow'];
      const SessionID = "487ba01b-d94c-4e22-84dc-4316e65854e2";
      let inputData = {};
      let outputDat = {};
      let tempJson = {};
      let tempList = [];
      let tempFloIn = {};
      let taskFid = "e5eb2da9-7c55-eb1e-a474-b44a65243a12";
      //"fe216d5e-f57c-c368-b86a-ca4e18bb456c"
      //let TaskFlowNameWithID = templateName + '_' + 'FarmerIp' + '_' + taskFid + '_User';
      let TaskFlowNameWithID = "FarmerInput_Report_FarmerFlow_User_e5eb2da9-7c55-eb1e-a474-b44a65243a12";

      tempList.push(TaskFlowNameWithID);
      tempJson[forumID] = tempList;
      let taskTempInFoCo = { "isDeleted": { "$ne": true } };
      taskTempInFoCo[ReplyBridgeID] = BridgeID;
      tempFloIn[TaskFlowNameWithID] = taskTempInFoCo;
      inputData[forumID] = tempFloIn;
      let taskTempOFoCo = { "_id": 0 };
      let tempFliOt = {};

      taskTempOFoCo["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_11"] = 1;
      taskTempOFoCo["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_12"] = 1;
      taskTempOFoCo["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_13"] = 1;
      taskTempOFoCo["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_15"] = 1;
      taskTempOFoCo["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_16"] = 1;
      taskTempOFoCo["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_17"] = 1;
      taskTempOFoCo["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_22"] = 1;
      taskTempOFoCo["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_23"] = 1;
      taskTempOFoCo["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_24"] = 1;
      taskTempOFoCo["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_25"] = 1;
      //taskTempOFoCo[templateName + "_TaskID_Main-665ad31e-25d6-8375-a2c7-b8963a5656b6_4"] = 1;

      tempFliOt[TaskFlowNameWithID] = taskTempOFoCo;
      outputDat[forumID] = tempFliOt;

      let jsonObject = {
        "MACAddress": userProfile.MACAddress,
        "SessionID": SessionID,
        "FlowNameIDList": tempJson,
        "ForumIDList": [forumID],
        "InputData": inputData,
        "OutputData": outputDat,
        "ServerID": "247366f9-f180-4c54-927d-0c008d07fff4-c8786a26-5320-439b-b0f7-aff6d1655525",
      }

      const payload = new FormData();
      payload.append("Data", JSON.stringify(jsonObject));
      const data = await generateReport(payload, "generateReport");
      if (data['ErrorCode'] === 1042) {
        const reportData = data['ErrorMessage'];
        let currentTaskId = 0;
        for (let i = 0; i < reportData.length; i++) {
          let mainKey = Object.keys(reportData[0][forumID]);
          let reports = reportData[0][forumID][mainKey[0]];
          let keys = Object.keys(reports);
          for (let j = 0; j < keys.length; j++) {
            
            const current = {
              name: decodeWithBase64(reports[j]["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_11"]),
              phone: decodeWithBase64(reports[j]["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_12"]),                
              district: decodeWithBase64(reports[j]["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_13"]),
              crop: decodeWithBase64(reports[j]["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_15"]),
              qty: decodeWithBase64(reports[j]["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_16"]),
              days: decodeWithBase64(reports[j]["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_17"]),
              village: decodeWithBase64(reports[j]["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_22"]),
              prefStorage: decodeWithBase64(reports[j]["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_23"]),
              notes: decodeWithBase64(reports[j]["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_24"]),
              confirm: decodeWithBase64(reports[j]["FarmerInput_FarmerFlow_Main-e3da967c-73ae-c885-936b-94aa199f2ed7_25"])
            };
            if (+current > currentTaskId) currentTaskId = +current;
          }
        }
        currentTaskId = ++currentTaskId;
        setTaskID(currentTaskId);
      }
    } catch (e) { }
}
