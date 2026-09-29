import { createContext, useContext, useState } from 'react'
import { translations } from '../i18n/translations'
import { staticTranslations } from '../i18n/staticTranslations'
import { useEffect } from 'react'

const LanguageContext = createContext(null)

export const LanguageProvider = ({ children }) => {
  const [lang, setLangState] = useState(() => localStorage.getItem('lang') || 'en')

  const setLang = (value) => {
    localStorage.setItem('lang', value)
    setLangState(value)
  }

  const t = (key) => translations[lang][key] || translations.en[key] || key

  useEffect(() => {
    const originals = new WeakMap()
    const translate = () => {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT)
      let node
      while ((node = walker.nextNode())) {
        const value = node.nodeValue.trim()
        if (!value) continue
        if (!originals.has(node)) originals.set(node, node.nodeValue)
        const original = originals.get(node)
        const clean = original.trim()
        const translated = lang === 'hi' ? staticTranslations[clean] : clean
        if (translated && translated !== clean) node.nodeValue = original.replace(clean, translated)
        else if (lang === 'en') node.nodeValue = original
      }
      document.querySelectorAll('[placeholder],[title],[aria-label]').forEach((el) => {
        if (!el.dataset.originalText) el.dataset.originalText = el.getAttribute('placeholder') || el.getAttribute('title') || el.getAttribute('aria-label') || ''
        const attr = el.hasAttribute('placeholder') ? 'placeholder' : el.hasAttribute('title') ? 'title' : 'aria-label'
        const original = el.dataset.originalText
        el.setAttribute(attr, lang === 'hi' ? (staticTranslations[original] || original) : original)
      })
    }
    translate()
    const observer = new MutationObserver(translate)
    observer.observe(document.body, { childList: true, subtree: true })
    return () => observer.disconnect()
  }, [lang])

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  )
}

export const useLanguage = () => useContext(LanguageContext)
