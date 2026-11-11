/* Composite export of already-recorded classroom trials. No inference or Core. */
(()=>{
  const canvas=document.createElement('canvas');canvas.width=1600;canvas.height=900;
  const paint=canvas.getContext('2d'),timeline=[];let at=0;
  const chapters=[];
  DATA.clips.forEach((clip,i)=>{
    const duration=clip.frames.length*.05+1;
    timeline.push({start:at,end:at+duration,index:i});
    if(!chapters.length||chapters.at(-1).source!==clip.evidence){
      chapters.push({start:at,end:at+duration,title:clip.title.split(' · ').slice(0,-2).join(' · '),source:clip.evidence});
    }else chapters.at(-1).end=at+duration;
    at+=duration;
  });
  function text(value,x,y,size=25,max=650){
    paint.fillStyle='#294c44';paint.font=size+'px system-ui';
    let line='',row=y;
    for(const char of String(value)){
      if(paint.measureText(line+char).width>max){paint.fillText(line,x,row);line='';row+=size*1.4;}
      line+=char;
    }
    paint.fillText(line,x,row);return row+size*1.5;
  }
  function frame(seconds,type='image/jpeg'){
    const t=Math.max(0,Math.min(seconds,at-.0001));
    const item=timeline.find(c=>t<c.end)||timeline.at(-1);
    index=item.index;pos=Math.min(DATA.clips[index].frames.length-1,Math.floor((t-item.start)/.05));playing=false;draw();
    const clip=DATA.clips[index],f=clip.frames[pos];
    paint.fillStyle='#fff';paint.fillRect(0,0,1600,900);
    text('THREEMIND / E56 / 原始记录回放',28,34,17,1500);
    text(clip.title,28,74,27,1540);
    paint.drawImage($('scene'),30,140,780,624);
    let y=text(clip.trial.text,845,176,31,720);
    y=text(f.action?'伺服执行读头所选位置':'感官输入；身体受环境风力作用',845,y+20,24,715);
    y=text('本题最终记录：'+clip.trial.answer,845,y+16,25,715);
    y=text(clip.trial.correct?'选对物体':'选错物体',845,y+12,30,715);
    text('实际视觉采样（另含深度输入）',845,430,24,715);
    paint.drawImage($('senses'),845,447,700,270);
    text('激活 '+f.activation.toFixed(3)+' · 抑制 '+f.inhibition.toFixed(3)+' · 联想触达 '+f.association.toFixed(3),845,745,21,715);
    text('第 '+(index+1)+' / '+DATA.clips.length+' 项 · '+f.time.toFixed(2)+' 模拟秒',30,820,23,1500);
    text('所有正确与错误均保留。所选位置来自活动读头；执行器不接收正确答案。',30,859,20,1530);
    return canvas.toDataURL(type,.9).split(',')[1];
  }
  window.classroomReplay={duration:at,chapters,title:'ThreeMind E56 全部指向与归因对照',frame};
})();
