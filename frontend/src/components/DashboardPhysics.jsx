import { useEffect, useRef } from 'react'
import Matter from 'matter-js'

/** Decorative, non-interactive physics layer for the dashboard. */
export default function DashboardPhysics() {
  const host = useRef(null)

  useEffect(() => {
    const element = host.current
    if (!element || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return undefined

    const { Engine, Render, Runner, Bodies, Composite, Events } = Matter
    const engine = Engine.create({ gravity: { x: 0, y: .18 } })
    const render = Render.create({
      element,
      engine,
      options: { width: element.clientWidth, height: element.clientHeight, wireframes: false, background: 'transparent', pixelRatio: window.devicePixelRatio || 1 },
    })
    const runner = Runner.create()
    const color = ['#55b8ae', '#78b5e5', '#e7ad64', '#a891d6']
    const width = element.clientWidth
    const height = element.clientHeight
    const bubbles = Array.from({ length: 14 }, (_, index) => Bodies.circle(
      40 + Math.random() * Math.max(20, width - 80),
      -Math.random() * height,
      7 + Math.random() * 15,
      { restitution: .85, friction: .001, frictionAir: .012, render: { fillStyle: color[index % color.length], opacity: .22 } },
    ))
    const walls = [
      Bodies.rectangle(width / 2, height + 20, width + 80, 40, { isStatic: true, render: { visible: false } }),
      Bodies.rectangle(-20, height / 2, 40, height * 2, { isStatic: true, render: { visible: false } }),
      Bodies.rectangle(width + 20, height / 2, 40, height * 2, { isStatic: true, render: { visible: false } }),
    ]
    Composite.add(engine.world, [...bubbles, ...walls])
    Render.run(render)
    Runner.run(runner, engine)

    const resize = () => {
      const nextWidth = element.clientWidth
      const nextHeight = element.clientHeight
      render.options.width = nextWidth; render.options.height = nextHeight
      render.canvas.width = nextWidth * render.options.pixelRatio
      render.canvas.height = nextHeight * render.options.pixelRatio
      render.canvas.style.width = `${nextWidth}px`; render.canvas.style.height = `${nextHeight}px`
      Matter.Body.setPosition(walls[0], { x: nextWidth / 2, y: nextHeight + 20 })
      Matter.Body.setPosition(walls[2], { x: nextWidth + 20, y: nextHeight / 2 })
    }
    window.addEventListener('resize', resize)
    Events.on(engine, 'beforeUpdate', () => bubbles.forEach((bubble) => {
      if (bubble.position.y > height + 40) Matter.Body.setPosition(bubble, { x: 35 + Math.random() * Math.max(20, width - 70), y: -20 })
    }))

    return () => {
      window.removeEventListener('resize', resize)
      Render.stop(render); Runner.stop(runner); Composite.clear(engine.world, false); Engine.clear(engine)
      render.canvas.remove(); render.textures = {}
    }
  }, [])

  return <div className="dashboard-physics" ref={host} aria-hidden="true" />
}
